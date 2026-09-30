from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal

os.environ.setdefault("VAPID_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("VAPID_PRIVATE_KEY", "test-private-key")

from pocketkid import create_app
from pocketkid.config import Settings
from pocketkid.extensions import db
from pocketkid.models import OperationRequest, RecurringMovement, Transaction, TransactionActorEvent, User, Wallet
from pocketkid.services import ensure_schema_updates, record_transaction_actor


class ActorTrackingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Settings.SQLALCHEMY_DATABASE_URI = "sqlite://"
        cls.app = create_app()
        cls.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        cls.client = cls.app.test_client()

    def setUp(self):
        with self.app.app_context():
            db.drop_all()
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()

    def seed_users(self, *, second_parent: bool = False) -> tuple[int, int, int | None]:
        with self.app.app_context():
            parent = User(username="parent", password_hash="unused", role="parent", preferred_language="en")
            child = User(username="child", password_hash="unused", role="child", preferred_language="en")
            users = [parent, child]
            other_parent = None
            if second_parent:
                other_parent = User(
                    username="other-parent",
                    password_hash="unused",
                    role="parent",
                    preferred_language="en",
                )
                users.append(other_parent)
            db.session.add_all(users)
            db.session.flush()
            db.session.add(Wallet(child_id=child.id, balance=Decimal("10.00"), minimum_balance=Decimal("-20.00")))
            db.session.commit()
            return parent.id, child.id, other_parent.id if other_parent else None

    def login_as(self, user_id: int) -> None:
        with self.client.session_transaction() as session:
            session["user_id"] = user_id

    def test_approved_request_records_created_and_approved_actor_events(self):
        parent_id, child_id, _ = self.seed_users()
        with self.app.app_context():
            operation_request = OperationRequest(
                request_type="withdrawal",
                status="pending",
                child_id=child_id,
                amount=Decimal("3.00"),
                description="Book",
            )
            db.session.add(operation_request)
            db.session.commit()
            request_id = operation_request.id

        self.login_as(parent_id)
        response = self.client.post(
            f"/parent/request/{request_id}/decision",
            data={"decision": "approve"},
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            transaction = Transaction.query.filter_by(child_id=child_id).one()
            events = TransactionActorEvent.query.filter_by(transaction_id=transaction.id).all()
            self.assertEqual({event.action for event in events}, {"created", "approved"})
            for event in events:
                self.assertEqual(event.actor_user_id, parent_id)
                self.assertEqual(event.actor_username, "parent")
                self.assertEqual(event.actor_role, "parent")

    def test_manual_transaction_records_only_created_action(self):
        parent_id, child_id, _ = self.seed_users()
        self.login_as(parent_id)

        response = self.client.post(
            f"/parent/child/{child_id}/manual",
            data={
                "movement": "deposit",
                "amount": "2.00",
                "deposit_mode": "free",
                "description": "Cash",
            },
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            event = TransactionActorEvent.query.one()
            self.assertEqual(event.action, "created")
            self.assertEqual(event.actor_username, "parent")

    def test_actor_snapshot_survives_user_rename_and_deletion(self):
        parent_id, child_id, _ = self.seed_users(second_parent=True)
        self.login_as(parent_id)
        self.client.post(
            f"/parent/child/{child_id}/manual",
            data={
                "movement": "deposit",
                "amount": "2.00",
                "deposit_mode": "free",
                "description": "Cash",
            },
        )

        with self.app.app_context():
            parent = db.session.get(User, parent_id)
            parent.username = "renamed-parent"
            db.session.commit()
            db.session.delete(parent)
            db.session.commit()

            event = TransactionActorEvent.query.one()
            self.assertEqual(event.actor_user_id, parent_id)
            self.assertEqual(event.actor_username, "parent")
            self.assertEqual(event.actor_role, "parent")

    def test_recurring_transaction_retains_deleted_configuring_parent(self):
        parent_id, child_id, other_parent_id = self.seed_users(second_parent=True)
        self.login_as(parent_id)
        tomorrow = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
        create_response = self.client.post(
            "/parent/recurring",
            data={
                "child_id": child_id,
                "movement": "deposit",
                "amount": "4.00",
                "frequency": "daily",
                "deposit_mode": "free",
                "description": "Allowance",
                "start_date": tomorrow,
            },
        )
        self.assertEqual(create_response.status_code, 302)

        self.login_as(other_parent_id)
        delete_response = self.client.post(
            f"/parent/parent/{parent_id}/delete",
            data={"double_confirmed": "1"},
        )
        self.assertEqual(delete_response.status_code, 302)

        with self.app.app_context():
            movement = RecurringMovement.query.one()
            self.assertEqual(movement.created_by_username, "parent")
            movement.next_run_at = datetime.now(UTC) - timedelta(minutes=1)
            db.session.commit()

        response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            event = TransactionActorEvent.query.one()
            self.assertEqual(event.actor_user_id, parent_id)
            self.assertEqual(event.actor_username, "parent")
            self.assertEqual(event.actor_role, "parent")

    def test_existing_transactions_are_backfilled_once(self):
        parent_id, child_id, _ = self.seed_users()
        with self.app.app_context():
            transaction = Transaction(
                child_id=child_id,
                kind="withdrawal",
                amount=Decimal("-1.00"),
                description="Historical withdrawal",
                created_by=parent_id,
            )
            db.session.add(transaction)
            db.session.commit()

            ensure_schema_updates()
            ensure_schema_updates()

            events = TransactionActorEvent.query.filter_by(transaction_id=transaction.id).all()
            self.assertEqual({event.action for event in events}, {"created", "approved"})
            self.assertEqual(len(events), 2)
            self.assertTrue(all(event.actor_username == "parent" for event in events))

    def test_recorder_supports_future_transaction_lifecycle_actions(self):
        parent_id, child_id, _ = self.seed_users()
        with self.app.app_context():
            transaction = Transaction(
                child_id=child_id,
                kind="parent_deposit",
                amount=Decimal("1.00"),
                description="Lifecycle",
                created_by=parent_id,
            )
            db.session.add(transaction)
            db.session.flush()
            for action in ("changed", "reversed", "deleted"):
                record_transaction_actor(
                    transaction=transaction,
                    action=action,
                    actor_user_id=parent_id,
                )
            db.session.commit()

            events = TransactionActorEvent.query.filter_by(transaction_id=transaction.id).all()
            self.assertEqual({event.action for event in events}, {"changed", "reversed", "deleted"})
            self.assertTrue(all(event.actor_username == "parent" for event in events))

    def test_child_deletion_removes_transaction_actor_events(self):
        parent_id, child_id, _ = self.seed_users()
        self.login_as(parent_id)
        self.client.post(
            f"/parent/child/{child_id}/manual",
            data={
                "movement": "deposit",
                "amount": "2.00",
                "deposit_mode": "free",
                "description": "Cash",
            },
        )

        response = self.client.post(
            f"/parent/child/{child_id}/delete",
            data={"double_confirmed": "1"},
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(TransactionActorEvent.query.count(), 0)
            self.assertEqual(Transaction.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
