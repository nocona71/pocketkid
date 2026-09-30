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

    def add_child_wallet(self, username: str, balance: str, minimum_balance: str = "0.00") -> int:
        with self.app.app_context():
            child = User(
                username=username,
                password_hash="unused",
                role="child",
                preferred_language="en",
            )
            db.session.add(child)
            db.session.flush()
            db.session.add(
                Wallet(
                    child_id=child.id,
                    balance=Decimal(balance),
                    minimum_balance=Decimal(minimum_balance),
                )
            )
            db.session.commit()
            return child.id

    def login_as(self, user_id: int):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id

    def test_approved_withdrawal_can_cross_zero(self):
        cases = (
            ("10.00", "0.00", "3.00", "7.00"),
            ("3.00", "0.00", "3.00", "0.00"),
            ("0.00", "-3.00", "2.00", "-2.00"),
            ("-2.00", "-5.00", "2.00", "-4.00"),
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

    def test_child_withdrawal_request_is_pending_and_bound_to_current_child(self):
        cases = (
            ("10.00", "0.00"),
            ("0.00", "0.00"),
            ("-3.00", "-10.00"),
        )

        for starting_balance, minimum_balance in cases:
            with self.subTest(starting_balance=starting_balance):
                self.setUp()
                parent_id, child_id = self.seed_wallet(starting_balance, minimum_balance)
                other_child_id = self.add_child_wallet("other-child", "50.00")
                description = f"Request from {starting_balance}"

                self.login_as(child_id)
                response = self.client.post(
                    "/child/request/withdrawal",
                    data={
                        "amount": "2.00",
                        "description": description,
                        "child_id": str(other_child_id),
                    },
                )

                self.assertEqual(response.status_code, 302)
                with self.app.app_context():
                    operation_request = OperationRequest.query.one()
                    self.assertEqual(operation_request.child_id, child_id)
                    self.assertEqual(operation_request.status, "pending")
                    self.assertEqual(operation_request.amount, Decimal("2.00"))
                    self.assertEqual(operation_request.description, description)
                    self.assertEqual(
                        Wallet.query.filter_by(child_id=child_id).one().balance,
                        Decimal(starting_balance),
                    )
                    self.assertEqual(
                        Wallet.query.filter_by(child_id=other_child_id).one().balance,
                        Decimal("50.00"),
                    )
                    self.assertEqual(Transaction.query.count(), 0)
                    self.assertEqual(
                        Notification.query.filter_by(
                            user_id=parent_id,
                            kind="approval_required",
                        ).count(),
                        1,
                    )

    def test_parent_rejects_child_withdrawal_without_moving_balance(self):
        parent_id, child_id = self.seed_wallet("3.00")
        self.login_as(child_id)
        response = self.client.post(
            "/child/request/withdrawal",
            data={"amount": "2.00", "description": "Rejected withdrawal"},
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            request_id = OperationRequest.query.one().id

        self.login_as(parent_id)
        response = self.client.post(
            f"/parent/request/{request_id}/decision",
            data={"decision": "reject"},
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            wallet = Wallet.query.filter_by(child_id=child_id).one()
            operation_request = db.session.get(OperationRequest, request_id)
            self.assertEqual(wallet.balance, Decimal("3.00"))
            self.assertEqual(operation_request.status, "rejected")
            self.assertEqual(operation_request.reviewed_by, parent_id)
            self.assertIsNotNone(operation_request.reviewed_at)
            self.assertEqual(Transaction.query.count(), 0)

    def test_child_dashboard_does_not_expose_another_child_records(self):
        parent_id, child_id = self.seed_wallet("12.34")
        other_child_id = self.add_child_wallet("other-child", "77.77")
        with self.app.app_context():
            db.session.add_all(
                [
                    OperationRequest(
                        request_type="withdrawal",
                        status="pending",
                        child_id=child_id,
                        amount=Decimal("1.00"),
                        description="Own private request",
                    ),
                    OperationRequest(
                        request_type="withdrawal",
                        status="pending",
                        child_id=other_child_id,
                        amount=Decimal("2.00"),
                        description="Other private request",
                    ),
                    Transaction(
                        child_id=child_id,
                        kind="withdrawal",
                        amount=Decimal("-1.00"),
                        description="Own private transaction",
                        created_by=parent_id,
                    ),
                    Transaction(
                        child_id=other_child_id,
                        kind="withdrawal",
                        amount=Decimal("-2.00"),
                        description="Other private transaction",
                        created_by=parent_id,
                    ),
                ]
            )
            db.session.commit()

        self.login_as(child_id)
        response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Own private request", response.data)
        self.assertIn(b"Own private transaction", response.data)
        self.assertNotIn(b"Other private request", response.data)
        self.assertNotIn(b"Other private transaction", response.data)
        self.assertNotIn(b"77.77", response.data)

        response = self.client.get(f"/parent/child/{other_child_id}")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/dashboard")

    def test_child_cannot_approve_or_directly_withdraw_from_another_child(self):
        _, child_id = self.seed_wallet("5.00")
        other_child_id = self.add_child_wallet("other-child", "8.00")
        with self.app.app_context():
            operation_request = OperationRequest(
                request_type="withdrawal",
                status="pending",
                child_id=other_child_id,
                amount=Decimal("3.00"),
                description="Other child withdrawal",
            )
            db.session.add(operation_request)
            db.session.commit()
            request_id = operation_request.id

        self.login_as(child_id)
        approval_response = self.client.post(
            f"/parent/request/{request_id}/decision",
            data={"decision": "approve"},
        )
        manual_response = self.client.post(
            f"/parent/child/{other_child_id}/manual",
            data={
                "movement": "withdraw",
                "amount": "3.00",
                "deposit_mode": "free",
                "description": "Unauthorized withdrawal",
            },
        )

        self.assertEqual(approval_response.status_code, 302)
        self.assertEqual(approval_response.headers["Location"], "/dashboard")
        self.assertEqual(manual_response.status_code, 302)
        self.assertEqual(manual_response.headers["Location"], "/dashboard")
        with self.app.app_context():
            wallet = Wallet.query.filter_by(child_id=other_child_id).one()
            operation_request = db.session.get(OperationRequest, request_id)
            self.assertEqual(wallet.balance, Decimal("8.00"))
            self.assertEqual(operation_request.status, "pending")
            self.assertIsNone(operation_request.reviewed_by)
            self.assertEqual(Transaction.query.count(), 0)

    def test_manual_withdrawal_can_cross_zero(self):
        cases = (
            ("10.00", "0.00", "3.00", "7.00"),
            ("3.00", "0.00", "3.00", "0.00"),
            ("0.00", "-3.00", "2.00", "-2.00"),
            ("-2.00", "-5.00", "2.00", "-4.00"),
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
            ("0.00", "-3.00", "2.00", "-2.00"),
            ("-2.00", "-5.00", "2.00", "-4.00"),
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
        self.assertIn(b"Minimum balance", response.data)
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

    def test_negative_balance_is_labeled_explicitly(self):
        parent_id, child_id = self.seed_wallet("-1.00", "-10.00")

        self.login_as(child_id)
        child_response = self.client.get("/dashboard")
        self.assertEqual(child_response.status_code, 200)
        self.assertIn(b"Negative balance", child_response.data)
        self.assertIn(b"\xe2\x82\xac -1.00", child_response.data)

        self.login_as(parent_id)
        for path in ("/dashboard", "/parent/children", f"/parent/child/{child_id}"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Negative balance", response.data)
                self.assertIn(b"\xe2\x82\xac -1.00", response.data)

    def test_balance_below_limit_shows_withdrawal_warning(self):
        parent_id, child_id = self.seed_wallet("-900.00", "0.00")

        self.login_as(child_id)
        child_response = self.client.get("/dashboard")
        self.assertEqual(child_response.status_code, 200)
        self.assertIn(b"Balance is \xe2\x82\xac 900.00 below the configured minimum.", child_response.data)
        self.assertIn(b"Further debits are blocked.", child_response.data)

        self.login_as(parent_id)
        parent_response = self.client.get(f"/parent/child/{child_id}")
        self.assertEqual(parent_response.status_code, 200)
        self.assertIn(b"Balance is \xe2\x82\xac 900.00 below the configured minimum.", parent_response.data)
        self.assertIn(b"Further debits are blocked.", parent_response.data)

    def test_balance_at_limit_does_not_show_withdrawal_warning(self):
        parent_id, child_id = self.seed_wallet("-10.00", "-10.00")

        self.login_as(child_id)
        child_response = self.client.get("/dashboard")
        self.assertEqual(child_response.status_code, 200)
        self.assertNotIn(b"Further debits are blocked.", child_response.data)

        self.login_as(parent_id)
        parent_response = self.client.get(f"/parent/child/{child_id}")
        self.assertEqual(parent_response.status_code, 200)
        self.assertNotIn(b"Further debits are blocked.", parent_response.data)


if __name__ == "__main__":
    unittest.main()
