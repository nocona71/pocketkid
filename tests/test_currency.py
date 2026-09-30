from __future__ import annotations

import os
import unittest
from decimal import Decimal

os.environ.setdefault("VAPID_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("VAPID_PRIVATE_KEY", "test-private-key")

from pocketkid import create_app
from pocketkid.config import Settings
from pocketkid.extensions import db
from pocketkid.models import AppSetting, Challenge, Notification, OperationRequest, Transaction, User, Wallet


class CurrencySettingsTests(unittest.TestCase):
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

    def seed_ledger(self) -> tuple[int, int]:
        with self.app.app_context():
            parent = User(username="parent", password_hash="unused", role="parent", preferred_language="en")
            child = User(username="child", password_hash="unused", role="child", preferred_language="en")
            db.session.add_all([parent, child])
            db.session.flush()
            db.session.add_all(
                [
                    Wallet(child_id=child.id, balance=Decimal("-12.34"), minimum_balance=Decimal("-20.00")),
                    Challenge(name="Chores", amount=Decimal("3.25"), active=True),
                    OperationRequest(
                        request_type="deposit",
                        status="pending",
                        child_id=child.id,
                        amount=Decimal("4.50"),
                        description="Top up",
                    ),
                    Transaction(
                        child_id=child.id,
                        kind="withdrawal",
                        amount=Decimal("-2.50"),
                        description="Purchase",
                        created_by=parent.id,
                    ),
                ]
            )
            db.session.commit()
            return parent.id, child.id

    def login_as(self, user_id: int) -> None:
        with self.client.session_transaction() as session:
            session["user_id"] = user_id

    def test_eur_is_the_backward_compatible_default(self):
        parent_id, _ = self.seed_ledger()
        self.login_as(parent_id)

        dashboard = self.client.get("/dashboard")
        settings = self.client.get("/settings")

        self.assertIn("€ -12.34".encode(), dashboard.data)
        self.assertIn("€ 4.50".encode(), dashboard.data)
        self.assertIn(b'<option value="EUR" selected>EUR (', settings.data)
        with self.app.app_context():
            self.assertIsNone(db.session.get(AppSetting, "currency"))

    def test_parent_change_updates_all_views_without_changing_stored_values(self):
        parent_id, child_id = self.seed_ledger()
        self.login_as(parent_id)

        response = self.client.post("/settings", data={"action": "currency", "currency": "USD"})

        self.assertEqual(response.status_code, 302)
        parent_dashboard = self.client.get("/dashboard")
        parent_wallet = self.client.get(f"/parent/child/{child_id}")
        self.login_as(child_id)
        child_dashboard = self.client.get("/dashboard")

        self.assertIn(b"$ -12.34", parent_dashboard.data)
        self.assertIn(b"$ 4.50", parent_dashboard.data)
        self.assertIn(b"$ -2.50", parent_wallet.data)
        self.assertIn(b"Minimum balance (USD)", parent_wallet.data)
        self.assertIn(b"Amount (USD)", parent_wallet.data)
        self.assertIn(b"$ -12.34", child_dashboard.data)
        self.assertIn(b"Amount (USD)", child_dashboard.data)

        with self.app.app_context():
            self.assertEqual(db.session.get(AppSetting, "currency").value, "USD")
            self.assertEqual(Wallet.query.filter_by(child_id=child_id).one().balance, Decimal("-12.34"))
            self.assertEqual(Transaction.query.filter_by(child_id=child_id).one().amount, Decimal("-2.50"))

    def test_child_cannot_change_currency(self):
        _, child_id = self.seed_ledger()
        self.login_as(child_id)

        response = self.client.post(
            "/settings",
            data={"action": "currency", "currency": "CHF"},
            follow_redirects=True,
        )

        self.assertIn(b"Permission denied", response.data)
        self.assertNotIn(b'name="currency"', response.data)
        with self.app.app_context():
            self.assertIsNone(db.session.get(AppSetting, "currency"))

    def test_invalid_currency_does_not_replace_current_setting(self):
        parent_id, _ = self.seed_ledger()
        self.login_as(parent_id)
        self.client.post("/settings", data={"action": "currency", "currency": "GBP"})

        response = self.client.post(
            "/settings",
            data={"action": "currency", "currency": "JPY"},
            follow_redirects=True,
        )

        self.assertIn(b"Invalid currency", response.data)
        with self.app.app_context():
            self.assertEqual(db.session.get(AppSetting, "currency").value, "GBP")

    def test_notifications_use_the_configured_currency(self):
        parent_id, child_id = self.seed_ledger()
        self.login_as(parent_id)
        self.client.post("/settings", data={"action": "currency", "currency": "GBP"})
        self.login_as(child_id)

        response = self.client.post(
            "/child/request/withdrawal",
            data={"amount": "2.75", "description": "Book"},
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            notification = Notification.query.filter_by(user_id=parent_id).order_by(Notification.id.desc()).first()
            self.assertIn("£ 2.75", notification.message)
            self.assertNotIn("€", notification.message)


if __name__ == "__main__":
    unittest.main()
