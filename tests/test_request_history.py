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
from pocketkid.models import OperationRequest, User, Wallet


class ChildRequestHistoryTests(unittest.TestCase):
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

    def seed_users(self, *, language: str = "en") -> tuple[int, int, int]:
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
                preferred_language=language,
            )
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
                    Wallet(child_id=child.id, balance=Decimal("0.00")),
                    Wallet(child_id=other_child.id, balance=Decimal("0.00")),
                ]
            )
            db.session.commit()
            return parent.id, child.id, other_child.id

    def add_requests(self, child_id: int, count: int, prefix: str) -> list[int]:
        created_at = datetime(2026, 1, 1, tzinfo=UTC)
        with self.app.app_context():
            requests = [
                OperationRequest(
                    request_type="withdrawal",
                    status="pending",
                    child_id=child_id,
                    amount=Decimal("1.00"),
                    description=f"{prefix}-{index:02d}",
                    created_at=created_at + timedelta(minutes=index),
                )
                for index in range(count)
            ]
            db.session.add_all(requests)
            db.session.commit()
            return [operation_request.id for operation_request in requests]

    def login_as(self, user_id: int) -> None:
        with self.client.session_transaction() as session:
            session["user_id"] = user_id

    def test_dashboard_shows_all_three_requests_without_history_action(self):
        _, child_id, _ = self.seed_users()
        self.add_requests(child_id, 3, "own")
        self.login_as(child_id)

        response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        for index in range(3):
            self.assertIn(f"own-{index:02d}".encode(), response.data)
        self.assertNotIn(b'href="/requests"', response.data)
        self.assertNotIn(b"View all requests", response.data)

    def test_dashboard_shows_three_newest_requests_and_history_action(self):
        _, child_id, _ = self.seed_users(language="de")
        self.add_requests(child_id, 4, "own")
        self.login_as(child_id)

        response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"own-00", response.data)
        for index in range(1, 4):
            self.assertIn(f"own-{index:02d}".encode(), response.data)
        self.assertIn(b'href="/requests"', response.data)
        self.assertIn("Alle Anfragen anzeigen".encode(), response.data)

    def test_history_is_paginated_and_scoped_to_authenticated_child(self):
        _, child_id, other_child_id = self.seed_users()
        own_request_ids = self.add_requests(child_id, 11, "own")
        self.add_requests(other_child_id, 2, "private")
        self.login_as(child_id)

        first_page = self.client.get("/requests")
        second_page = self.client.get("/requests?page=2")

        self.assertEqual(first_page.status_code, 200)
        self.assertIn(b"Request history", first_page.data)
        self.assertIn(b'href="/dashboard"', first_page.data)
        self.assertIn(b'href="/requests?page=2"', first_page.data)
        self.assertIn(b"1/2", first_page.data)
        self.assertNotIn(b"own-00", first_page.data)
        for index in range(1, 11):
            self.assertIn(f"own-{index:02d}".encode(), first_page.data)
        self.assertEqual(second_page.status_code, 200)
        self.assertIn(b"own-00", second_page.data)
        self.assertIn(b"2/2", second_page.data)
        self.assertIn(
            f'href="/requests/{own_request_ids[0]}"'.encode(),
            second_page.data,
        )
        for response in (first_page, second_page):
            self.assertNotIn(b"private-", response.data)

    def test_history_route_rejects_parent_and_signed_out_users(self):
        parent_id, _, _ = self.seed_users()

        signed_out = self.client.get("/requests")
        self.login_as(parent_id)
        parent = self.client.get("/requests")

        self.assertEqual(signed_out.status_code, 302)
        self.assertEqual(signed_out.headers["Location"], "/login")
        self.assertEqual(parent.status_code, 302)
        self.assertEqual(parent.headers["Location"], "/dashboard")


if __name__ == "__main__":
    unittest.main()
