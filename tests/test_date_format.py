from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime
from decimal import Decimal

os.environ.setdefault("VAPID_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("VAPID_PRIVATE_KEY", "test-private-key")

from pocketkid import create_app
from pocketkid.config import Settings
from pocketkid.extensions import db
from pocketkid.models import (
    AppSetting,
    Challenge,
    Notification,
    OperationRequest,
    PushSubscription,
    RecurringMovement,
    Transaction,
    TransactionActorEvent,
    User,
    Wallet,
)


class DateFormatSettingsTests(unittest.TestCase):
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

    def seed_ledger(self) -> dict[str, int]:
        displayed_at = datetime(2026, 9, 30, 10, 7, tzinfo=UTC)
        next_run_at = datetime(2030, 1, 2, 0, 0, tzinfo=UTC)

        with self.app.app_context():
            parent = User(username="parent", password_hash="unused", role="parent", preferred_language="en")
            child = User(username="child", password_hash="unused", role="child", preferred_language="en")
            db.session.add_all([parent, child])
            db.session.flush()

            challenge = Challenge(
                name="Chores",
                amount=Decimal("3.00"),
                created_at=displayed_at,
            )
            operation_request = OperationRequest(
                request_type="deposit",
                status="pending",
                child_id=child.id,
                amount=Decimal("4.00"),
                description="Birthday gift",
                created_at=displayed_at,
                reviewed_at=displayed_at,
                reviewed_by=parent.id,
            )
            transaction = Transaction(
                child_id=child.id,
                kind="parent_deposit",
                amount=Decimal("5.00"),
                description="Opening entry",
                created_at=displayed_at,
                created_by=parent.id,
            )
            db.session.add_all(
                [
                    Wallet(child_id=child.id, balance=Decimal("5.00")),
                    challenge,
                    operation_request,
                    transaction,
                    Notification(
                        user_id=parent.id,
                        kind="test",
                        message="Date test",
                        created_at=displayed_at,
                    ),
                    RecurringMovement(
                        child_id=child.id,
                        movement="deposit",
                        amount=Decimal("1.00"),
                        frequency="monthly",
                        description="Monthly entry",
                        next_run_at=next_run_at,
                        created_by=parent.id,
                        created_by_username=parent.username,
                        created_by_role=parent.role,
                    ),
                    PushSubscription(
                        user_id=parent.id,
                        endpoint="https://example.test/push",
                        p256dh="key",
                        auth="auth",
                        created_at=displayed_at,
                        last_seen_at=displayed_at,
                    ),
                ]
            )
            db.session.flush()
            db.session.add(
                TransactionActorEvent(
                    transaction_id=transaction.id,
                    action="created",
                    actor_user_id=parent.id,
                    actor_username=parent.username,
                    actor_role=parent.role,
                    occurred_at=displayed_at,
                )
            )
            db.session.commit()
            return {
                "parent_id": parent.id,
                "child_id": child.id,
                "request_id": operation_request.id,
                "transaction_id": transaction.id,
            }

    def login_as(self, user_id: int) -> None:
        with self.client.session_transaction() as session:
            session["user_id"] = user_id

    def test_default_format_preserves_existing_display(self):
        ids = self.seed_ledger()
        self.login_as(ids["parent_id"])

        dashboard = self.client.get("/dashboard")
        settings = self.client.get("/settings")

        self.assertIn(b"30/09/2026 10:07", dashboard.data)
        self.assertIn(b'<option value="DD/MM/YYYY" selected>', settings.data)
        with self.app.app_context():
            self.assertIsNone(db.session.get(AppSetting, "date_format"))

    def test_parent_change_updates_dates_in_views_and_json_without_changing_storage(self):
        ids = self.seed_ledger()
        self.login_as(ids["parent_id"])

        response = self.client.post(
            "/settings",
            data={"action": "date_format", "date_format": "YYYY-MM-DD"},
        )

        self.assertEqual(response.status_code, 302)
        for path in (
            "/dashboard",
            f"/parent/child/{ids['child_id']}",
            f"/transactions/{ids['transaction_id']}",
            f"/requests/{ids['request_id']}",
        ):
            with self.subTest(path=path):
                page = self.client.get(path)
                self.assertEqual(page.status_code, 200)
                self.assertIn(b"2026-09-30 10:07", page.data)

        challenges = self.client.get("/parent/challenges")
        recurring = self.client.get("/parent/recurring")
        notifications = self.client.get("/api/notifications").get_json()
        push_debug = self.client.get("/api/push/debug").get_json()

        self.assertIn(b"2026-09-30", challenges.data)
        self.assertIn(b"2030-01-02", recurring.data)
        self.assertEqual(notifications["items"][0]["created_at"], "2026-09-30 10:07")
        self.assertEqual(push_debug["subscriptions"][0]["createdAt"], "2026-09-30 10:07")
        self.assertEqual(push_debug["subscriptions"][0]["lastSeenAt"], "2026-09-30 10:07")

        self.login_as(ids["child_id"])
        child_dashboard = self.client.get("/dashboard")
        self.assertIn(b"2026-09-30 10:07", child_dashboard.data)

        with self.app.app_context():
            self.assertEqual(db.session.get(AppSetting, "date_format").value, "YYYY-MM-DD")
            stored = db.session.get(Transaction, ids["transaction_id"]).created_at
            self.assertEqual(stored, datetime(2026, 9, 30, 10, 7))

    def test_each_supported_format_controls_the_date_component(self):
        ids = self.seed_ledger()
        self.login_as(ids["parent_id"])

        for date_format, expected in (
            ("DD/MM/YYYY", b"30/09/2026 10:07"),
            ("DD.MM.YYYY", b"30.09.2026 10:07"),
            ("MM/DD/YYYY", b"09/30/2026 10:07"),
            ("YYYY-MM-DD", b"2026-09-30 10:07"),
        ):
            with self.subTest(date_format=date_format):
                response = self.client.post(
                    "/settings",
                    data={"action": "date_format", "date_format": date_format},
                )
                self.assertEqual(response.status_code, 302)
                self.assertIn(expected, self.client.get("/dashboard").data)

    def test_child_cannot_change_date_format(self):
        ids = self.seed_ledger()
        self.login_as(ids["child_id"])

        response = self.client.post(
            "/settings",
            data={"action": "date_format", "date_format": "MM/DD/YYYY"},
            follow_redirects=True,
        )

        self.assertIn(b"Permission denied", response.data)
        self.assertNotIn(b'name="date_format"', response.data)
        with self.app.app_context():
            self.assertIsNone(db.session.get(AppSetting, "date_format"))

    def test_invalid_format_does_not_replace_current_setting(self):
        ids = self.seed_ledger()
        self.login_as(ids["parent_id"])
        self.client.post(
            "/settings",
            data={"action": "date_format", "date_format": "DD.MM.YYYY"},
        )

        response = self.client.post(
            "/settings",
            data={"action": "date_format", "date_format": "%c"},
            follow_redirects=True,
        )

        self.assertIn(b"Invalid date format", response.data)
        with self.app.app_context():
            self.assertEqual(db.session.get(AppSetting, "date_format").value, "DD.MM.YYYY")


if __name__ == "__main__":
    unittest.main()
