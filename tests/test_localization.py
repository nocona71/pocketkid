from __future__ import annotations

import json
import os
import string
import unittest

os.environ.setdefault("VAPID_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("VAPID_PRIVATE_KEY", "test-private-key")

from pocketkid import create_app
from pocketkid.config import LOCALES_DIR, SUPPORTED_LANGUAGES, Settings
from pocketkid.extensions import db
from pocketkid.models import User


class LocaleCatalogTests(unittest.TestCase):
    def test_catalogs_have_matching_keys_and_placeholders(self):
        catalogs = {
            language: json.loads((LOCALES_DIR / f"{language}.json").read_text(encoding="utf-8"))
            for language in SUPPORTED_LANGUAGES
        }
        english_keys = set(catalogs["en"])

        for language, catalog in catalogs.items():
            with self.subTest(language=language):
                self.assertEqual(set(catalog), english_keys)
                for key, english_value in catalogs["en"].items():
                    english_fields = {
                        field_name
                        for _, field_name, _, _ in string.Formatter().parse(english_value)
                        if field_name
                    }
                    translated_fields = {
                        field_name
                        for _, field_name, _, _ in string.Formatter().parse(catalog[key])
                        if field_name
                    }
                    self.assertEqual(translated_fields, english_fields, key)

    def test_push_ui_has_no_hard_coded_italian_labels(self):
        javascript = (LOCALES_DIR.parent / "static/js/app.js").read_text(encoding="utf-8")

        for literal in (
            "Attive",
            "Disattiva Notifiche Push",
            "Attiva Notifiche Push",
            "Permesso concesso",
            "Impossibile verificare",
            "Notifiche disattivate",
            "Verifica in corso",
        ):
            with self.subTest(literal=literal):
                self.assertNotIn(literal, javascript)


class GermanLocalizationTests(unittest.TestCase):
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

    def test_browser_language_detection_uses_german(self):
        response = self.client.get("/setup", headers={"Accept-Language": "de-DE,de;q=0.9,en;q=0.8"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<html lang="de">', response.data)
        self.assertIn("Ersteinrichtung".encode(), response.data)
        self.assertIn(b'<option value="de">Deutsch</option>', response.data)

    def test_german_user_sees_localized_settings_and_push_labels(self):
        with self.app.app_context():
            parent = User(
                username="parent",
                password_hash="unused",
                role="parent",
                preferred_language="de",
            )
            db.session.add(parent)
            db.session.commit()
            parent_id = parent.id

        with self.client.session_transaction() as session:
            session["user_id"] = parent_id

        response = self.client.get("/settings")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<html lang="de">', response.data)
        self.assertIn("Push-Benachrichtigungen".encode(), response.data)
        self.assertIn(b'data-disable-button="Push-Benachrichtigungen deaktivieren"', response.data)
        self.assertNotIn(b"<hr", response.data)

    def test_setup_persists_german_preference(self):
        response = self.client.post(
            "/setup",
            data={
                "parent_username": "eltern",
                "parent_password": "secret",
                "parent_language": "de",
            },
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(User.query.one().preferred_language, "de")


if __name__ == "__main__":
    unittest.main()
