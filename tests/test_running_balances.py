from __future__ import annotations

import os
import re
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal

os.environ.setdefault("VAPID_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("VAPID_PRIVATE_KEY", "test-private-key")

from pocketkid import create_app
from pocketkid.config import Settings
from pocketkid.extensions import db
from pocketkid.models import Transaction, User, Wallet
from pocketkid.services import get_transaction_running_balances


class RunningBalanceHistoryTests(unittest.TestCase):
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

    def seed_ledger(self) -> dict[str, object]:
        amounts = (
            Decimal("10.00"),
            Decimal("-15.00"),
            Decimal("-3.00"),
            Decimal("7.00"),
            Decimal("-1.00"),
            Decimal("2.00"),
            Decimal("-8.00"),
            Decimal("12.00"),
            Decimal("-4.00"),
            Decimal("1.00"),
            Decimal("-10.00"),
            Decimal("5.00"),
        )
        expected = (
            Decimal("15.00"),
            Decimal("0.00"),
            Decimal("-3.00"),
            Decimal("4.00"),
            Decimal("3.00"),
            Decimal("5.00"),
            Decimal("-3.00"),
            Decimal("9.00"),
            Decimal("5.00"),
            Decimal("6.00"),
            Decimal("-4.00"),
            Decimal("1.00"),
        )
        first_timestamp = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)

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
                    Wallet(child_id=child.id, balance=Decimal("1.00")),
                    Wallet(child_id=other_child.id, balance=Decimal("999.00")),
                ]
            )

            transactions = []
            for index, amount in enumerate(amounts, start=1):
                timestamp = first_timestamp + timedelta(days=min(index - 1, 10))
                transaction = Transaction(
                    child_id=child.id,
                    kind="parent_deposit" if amount >= 0 else "withdrawal",
                    amount=amount,
                    description=f"Entry {index:02d}",
                    created_at=timestamp,
                    created_by=parent.id,
                )
                db.session.add(transaction)
                transactions.append(transaction)

            db.session.add(
                Transaction(
                    child_id=other_child.id,
                    kind="parent_deposit",
                    amount=Decimal("999.00"),
                    description="Other private entry",
                    created_at=first_timestamp,
                    created_by=parent.id,
                )
            )
            db.session.commit()
            return {
                "parent_id": parent.id,
                "child_id": child.id,
                "transaction_ids": [transaction.id for transaction in transactions],
                "expected": expected,
            }

    def login_as(self, user_id: int) -> None:
        with self.client.session_transaction() as session:
            session["user_id"] = user_id

    def test_calculation_infers_opening_balance_and_crosses_zero(self):
        ledger = self.seed_ledger()

        with self.app.app_context():
            balances = get_transaction_running_balances(
                ledger["child_id"],
                Decimal("1.00"),
            )

        self.assertEqual(
            [balances[transaction_id] for transaction_id in ledger["transaction_ids"]],
            list(ledger["expected"]),
        )
        self.assertIn(Decimal("0.00"), balances.values())
        self.assertIn(Decimal("-4.00"), balances.values())
        self.assertEqual(balances[ledger["transaction_ids"][-1]], Decimal("1.00"))

    def test_parent_and_child_see_same_balances_on_paginated_history(self):
        ledger = self.seed_ledger()
        self.login_as(ledger["parent_id"])
        parent_page = self.client.get(f"/parent/child/{ledger['child_id']}?page=2")

        self.login_as(ledger["child_id"])
        child_page = self.client.get("/dashboard?transactions_page=2")

        for response in (parent_page, child_page):
            with self.subTest(path=response.request.path):
                self.assertEqual(response.status_code, 200)
                html = response.data.decode()
                self.assertLess(html.index("Entry 02"), html.index("Entry 01"))
                self.assertRegex(
                    html,
                    re.compile(
                        r"Entry 02.*?€ -15\.00</p>\s*"
                        r'<p class="muted resulting-balance">Balance: € 0\.00</p>',
                        re.DOTALL,
                    ),
                )
                self.assertIn("Balance: € 15.00", html)
                self.assertNotIn("Other private entry", html)
                self.assertNotIn("Balance: € 999.00", html)

    def test_equal_timestamps_use_transaction_id_as_tie_breaker(self):
        ledger = self.seed_ledger()
        self.login_as(ledger["parent_id"])

        response = self.client.get(f"/parent/child/{ledger['child_id']}")
        html = response.data.decode()

        self.assertLess(html.index("Entry 12"), html.index("Entry 11"))
        self.assertIn("Balance: € -4.00", html)
        self.assertIn("Balance: € 1.00", html)


if __name__ == "__main__":
    unittest.main()
