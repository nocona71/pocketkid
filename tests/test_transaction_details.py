from __future__ import annotations

import os
import unittest
from decimal import Decimal

os.environ.setdefault("VAPID_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("VAPID_PRIVATE_KEY", "test-private-key")

from pocketkid import create_app
from pocketkid.config import Settings
from pocketkid.extensions import db
from pocketkid.models import User, Wallet
from pocketkid.services import register_transaction


class TransactionDetailsTests(unittest.TestCase):
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
        with self.client.session_transaction() as session:
            session.clear()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()

    def seed_ledger(self) -> tuple[int, int, int, int, int]:
        with self.app.app_context():
            parent = User(username="parent", password_hash="unused", role="parent", preferred_language="en")
            child = User(username="child", password_hash="unused", role="child", preferred_language="en")
            other_child = User(
                username="other-child",
                password_hash="unused",
                role="child",
                preferred_language="en",
            )
            db.session.add_all([parent, child, other_child])
            db.session.flush()
            db.session.add_all(
                [
                    Wallet(child_id=child.id, balance=Decimal("6.50")),
                    Wallet(child_id=other_child.id, balance=Decimal("8.00")),
                ]
            )
            approved = register_transaction(
                child_id=child.id,
                kind="withdrawal",
                amount=Decimal("-3.50"),
                description="Library book",
                created_by=parent.id,
                additional_actor_actions=("approved",),
            )
            direct = register_transaction(
                child_id=other_child.id,
                kind="parent_deposit",
                amount=Decimal("8.00"),
                description="Private gift",
                created_by=parent.id,
            )
            db.session.commit()
            return parent.id, child.id, other_child.id, approved.id, direct.id

    def login_as(self, user_id: int) -> None:
        with self.client.session_transaction() as session:
            session["user_id"] = user_id

    def test_parent_sees_complete_approved_transaction_details(self):
        parent_id, _, _, transaction_id, _ = self.seed_ledger()
        self.login_as(parent_id)

        response = self.client.get(f"/transactions/{transaction_id}")

        self.assertEqual(response.status_code, 200)
        for expected in (
            b"Transaction details",
            b"Account",
            b"Child",
            b"Transaction type",
            b"Withdrawal",
            b"\xe2\x82\xac -3.50",
            b"Date and time",
            b"Library book",
            b"Creator",
            b"Parent \xc2\xb7 Parent",
            b"Approval status",
            b"Audit history",
            b"Created",
            b"Approved",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, response.data)

    def test_direct_transaction_is_marked_as_not_requiring_approval(self):
        parent_id, _, _, _, transaction_id = self.seed_ledger()
        self.login_as(parent_id)

        response = self.client.get(f"/transactions/{transaction_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Parent deposit", response.data)
        self.assertIn(b"Not required", response.data)
        self.assertNotIn(b"actor_action_", response.data)

    def test_child_can_open_own_transaction_from_history(self):
        _, child_id, _, transaction_id, _ = self.seed_ledger()
        self.login_as(child_id)

        dashboard = self.client.get("/dashboard")
        details = self.client.get(f"/transactions/{transaction_id}")

        self.assertIn(f'href="/transactions/{transaction_id}"'.encode(), dashboard.data)
        self.assertEqual(details.status_code, 200)
        self.assertIn(b"Library book", details.data)
        self.assertNotIn(b"<dt>Account</dt>", details.data)

    def test_child_cannot_view_another_child_transaction(self):
        _, child_id, _, _, other_transaction_id = self.seed_ledger()
        self.login_as(child_id)

        response = self.client.get(
            f"/transactions/{other_transaction_id}",
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Transaction not found", response.data)
        self.assertNotIn(b"Private gift", response.data)
        self.assertNotIn(b"Other-child", response.data)

    def test_parent_history_links_to_transaction_details(self):
        parent_id, child_id, _, transaction_id, _ = self.seed_ledger()
        self.login_as(parent_id)

        response = self.client.get(f"/parent/child/{child_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(f'href="/transactions/{transaction_id}"'.encode(), response.data)

    def test_signed_out_user_is_redirected_to_login(self):
        _, _, _, transaction_id, _ = self.seed_ledger()

        response = self.client.get(f"/transactions/{transaction_id}")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")


if __name__ == "__main__":
    unittest.main()
