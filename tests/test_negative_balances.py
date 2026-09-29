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
from pocketkid.models import Notification, OperationRequest, RecurringMovement, Transaction, User, Wallet


class NegativeBalanceTests(unittest.TestCase):
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

    def seed_wallet(self, balance: str, minimum_balance: str | None = None) -> tuple[int, int]:
        with self.app.app_context():
            parent = User(
                username="parent",
                password_hash="unused",
                role="parent",
                preferred_language="en",
            )
            child = User(
                username="child",
                password_hash="unused",
                role="child",
                preferred_language="en",
            )
            db.session.add_all([parent, child])
            db.session.flush()
            wallet = Wallet(child_id=child.id, balance=Decimal(balance))
            if minimum_balance is not None:
                wallet.minimum_balance = Decimal(minimum_balance)
            db.session.add(wallet)
            db.session.commit()
            return parent.id, child.id

    def login_as(self, user_id: int):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id

    def test_approved_withdrawal_can_cross_zero(self):
        cases = (
            ("10.00", "0.00", "3.00", "7.00"),
            ("3.00", "0.00", "3.00", "0.00"),
            ("2.00", "-1.00", "3.00", "-1.00"),
        )

        for starting_balance, minimum_balance, amount, expected_balance in cases:
            with self.subTest(expected_balance=expected_balance):
                self.setUp()
                parent_id, child_id = self.seed_wallet(starting_balance, minimum_balance)
                with self.app.app_context():
                    operation_request = OperationRequest(
                        request_type="withdrawal",
                        status="pending",
                        child_id=child_id,
                        amount=Decimal(amount),
                        description="Approved withdrawal",
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
                    wallet = Wallet.query.filter_by(child_id=child_id).one()
                    operation_request = db.session.get(OperationRequest, request_id)
                    transaction = Transaction.query.filter_by(child_id=child_id).one()
                    self.assertEqual(wallet.balance, Decimal(expected_balance))
                    self.assertEqual(operation_request.status, "approved")
                    self.assertEqual(operation_request.reviewed_by, parent_id)
                    self.assertEqual(transaction.amount, -Decimal(amount))
                    self.assertEqual(transaction.created_by, parent_id)

    def test_manual_withdrawal_can_cross_zero(self):
        cases = (
            ("10.00", "0.00", "3.00", "7.00"),
            ("3.00", "0.00", "3.00", "0.00"),
            ("2.00", "-1.00", "3.00", "-1.00"),
        )

        for starting_balance, minimum_balance, amount, expected_balance in cases:
            with self.subTest(expected_balance=expected_balance):
                self.setUp()
                parent_id, child_id = self.seed_wallet(starting_balance, minimum_balance)
                self.login_as(parent_id)

                response = self.client.post(
                    f"/parent/child/{child_id}/manual",
                    data={
                        "movement": "withdraw",
                        "amount": amount,
                        "deposit_mode": "free",
                        "description": "Manual withdrawal",
                    },
                )

                self.assertEqual(response.status_code, 302)
                with self.app.app_context():
                    wallet = Wallet.query.filter_by(child_id=child_id).one()
                    transaction = Transaction.query.filter_by(child_id=child_id).one()
                    self.assertEqual(wallet.balance, Decimal(expected_balance))
                    self.assertEqual(transaction.kind, "parent_withdrawal")
                    self.assertEqual(transaction.amount, -Decimal(amount))
                    self.assertEqual(transaction.created_by, parent_id)

    def test_recurring_withdrawal_can_cross_zero(self):
        cases = (
            ("10.00", "0.00", "3.00", "7.00"),
            ("3.00", "0.00", "3.00", "0.00"),
            ("2.00", "-1.00", "3.00", "-1.00"),
        )

        for starting_balance, minimum_balance, amount, expected_balance in cases:
            with self.subTest(expected_balance=expected_balance):
                self.setUp()
                parent_id, child_id = self.seed_wallet(starting_balance, minimum_balance)
                with self.app.app_context():
                    movement = RecurringMovement(
                        child_id=child_id,
                        movement="withdraw",
                        amount=Decimal(amount),
                        frequency="daily",
                        description="Recurring withdrawal",
                        deposit_mode="free",
                        next_run_at=datetime.now(UTC) - timedelta(minutes=1),
                        created_by=parent_id,
                    )
                    db.session.add(movement)
                    db.session.commit()
                    movement_id = movement.id

                self.login_as(parent_id)
                response = self.client.get("/dashboard")

                self.assertEqual(response.status_code, 200)
                with self.app.app_context():
                    wallet = Wallet.query.filter_by(child_id=child_id).one()
                    movement = db.session.get(RecurringMovement, movement_id)
                    transaction = Transaction.query.filter_by(child_id=child_id).one()
                    self.assertEqual(wallet.balance, Decimal(expected_balance))
                    self.assertEqual(transaction.kind, "recurring_withdraw")
                    self.assertEqual(transaction.amount, -Decimal(amount))
                    self.assertGreater(movement.next_run_at, datetime.now(UTC).replace(tzinfo=None))
                    self.assertIsNone(Notification.query.filter_by(kind="recurring_failed").first())

    def test_default_zero_limit_blocks_approved_withdrawal(self):
        parent_id, child_id = self.seed_wallet("2.00")
        with self.app.app_context():
            wallet = Wallet.query.filter_by(child_id=child_id).one()
            self.assertEqual(wallet.minimum_balance, Decimal("0.00"))
            operation_request = OperationRequest(
                request_type="withdrawal",
                status="pending",
                child_id=child_id,
                amount=Decimal("3.00"),
                description="Blocked withdrawal",
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
            wallet = Wallet.query.filter_by(child_id=child_id).one()
            operation_request = db.session.get(OperationRequest, request_id)
            self.assertEqual(wallet.balance, Decimal("2.00"))
            self.assertEqual(operation_request.status, "pending")
            self.assertIsNone(operation_request.reviewed_by)
            self.assertEqual(Transaction.query.filter_by(child_id=child_id).count(), 0)

    def test_default_zero_limit_blocks_manual_withdrawal(self):
        parent_id, child_id = self.seed_wallet("2.00")
        self.login_as(parent_id)

        response = self.client.post(
            f"/parent/child/{child_id}/manual",
            data={
                "movement": "withdraw",
                "amount": "3.00",
                "deposit_mode": "free",
                "description": "Blocked manual withdrawal",
            },
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            wallet = Wallet.query.filter_by(child_id=child_id).one()
            self.assertEqual(wallet.balance, Decimal("2.00"))
            self.assertEqual(Transaction.query.filter_by(child_id=child_id).count(), 0)

    def test_default_zero_limit_skips_recurring_withdrawal(self):
        parent_id, child_id = self.seed_wallet("2.00")
        with self.app.app_context():
            previous_run = datetime.now(UTC) - timedelta(minutes=1)
            movement = RecurringMovement(
                child_id=child_id,
                movement="withdraw",
                amount=Decimal("3.00"),
                frequency="daily",
                description="Blocked recurring withdrawal",
                deposit_mode="free",
                next_run_at=previous_run,
                created_by=parent_id,
            )
            db.session.add(movement)
            db.session.commit()
            movement_id = movement.id

        self.login_as(parent_id)
        response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            wallet = Wallet.query.filter_by(child_id=child_id).one()
            movement = db.session.get(RecurringMovement, movement_id)
            notification = Notification.query.filter_by(kind="recurring_failed").one()
            self.assertEqual(wallet.balance, Decimal("2.00"))
            self.assertEqual(Transaction.query.filter_by(child_id=child_id).count(), 0)
            self.assertGreater(movement.next_run_at, previous_run.replace(tzinfo=None))
            self.assertIn("0.00", notification.message)

    def test_parent_can_update_limit_and_child_can_see_it(self):
        parent_id, child_id = self.seed_wallet("0.00")
        self.login_as(parent_id)

        response = self.client.post(
            f"/parent/child/{child_id}/minimum-balance",
            data={"minimum_balance": "-25.50"},
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            wallet = Wallet.query.filter_by(child_id=child_id).one()
            self.assertEqual(wallet.minimum_balance, Decimal("-25.50"))

        self.login_as(child_id)
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Overdraft limit", response.data)
        self.assertIn(b"\xe2\x82\xac -25.50", response.data)

    def test_child_cannot_update_limit(self):
        _, child_id = self.seed_wallet("0.00")
        self.login_as(child_id)

        response = self.client.post(
            f"/parent/child/{child_id}/minimum-balance",
            data={"minimum_balance": "-25.50"},
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            wallet = Wallet.query.filter_by(child_id=child_id).one()
            self.assertEqual(wallet.minimum_balance, Decimal("0.00"))

    def test_positive_limit_is_rejected(self):
        parent_id, child_id = self.seed_wallet("0.00", "-10.00")
        self.login_as(parent_id)

        response = self.client.post(
            f"/parent/child/{child_id}/minimum-balance",
            data={"minimum_balance": "5.00"},
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            wallet = Wallet.query.filter_by(child_id=child_id).one()
            self.assertEqual(wallet.minimum_balance, Decimal("-10.00"))

    def test_negative_balance_is_labeled_as_debt(self):
        parent_id, child_id = self.seed_wallet("-1.00", "-10.00")

        self.login_as(child_id)
        child_response = self.client.get("/dashboard")
        self.assertEqual(child_response.status_code, 200)
        self.assertIn(b"Debt", child_response.data)
        self.assertIn(b"\xe2\x82\xac -1.00", child_response.data)

        self.login_as(parent_id)
        for path in ("/dashboard", "/parent/children", f"/parent/child/{child_id}"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Debt", response.data)
                self.assertIn(b"\xe2\x82\xac -1.00", response.data)

    def test_balance_below_limit_shows_withdrawal_warning(self):
        parent_id, child_id = self.seed_wallet("-900.00", "0.00")

        self.login_as(child_id)
        child_response = self.client.get("/dashboard")
        self.assertEqual(child_response.status_code, 200)
        self.assertIn(b"Overdraft limit exceeded by \xe2\x82\xac 900.00.", child_response.data)
        self.assertIn(b"Further withdrawals are blocked.", child_response.data)

        self.login_as(parent_id)
        parent_response = self.client.get(f"/parent/child/{child_id}")
        self.assertEqual(parent_response.status_code, 200)
        self.assertIn(b"Overdraft limit exceeded by \xe2\x82\xac 900.00.", parent_response.data)
        self.assertIn(b"Further withdrawals are blocked.", parent_response.data)

    def test_balance_at_limit_does_not_show_withdrawal_warning(self):
        parent_id, child_id = self.seed_wallet("-10.00", "-10.00")

        self.login_as(child_id)
        child_response = self.client.get("/dashboard")
        self.assertEqual(child_response.status_code, 200)
        self.assertNotIn(b"Further withdrawals are blocked.", child_response.data)

        self.login_as(parent_id)
        parent_response = self.client.get(f"/parent/child/{child_id}")
        self.assertEqual(parent_response.status_code, 200)
        self.assertNotIn(b"Further withdrawals are blocked.", parent_response.data)


if __name__ == "__main__":
    unittest.main()
