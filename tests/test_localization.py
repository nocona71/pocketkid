from __future__ import annotations

import json
import os
import string
import unittest

os.environ.setdefault("VAPID_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("VAPID_PRIVATE_KEY", "test-private-key")

from pocketkid import create_app
from pocketkid.config import LOCALES_DIR, PROJECT_VERSION, SUPPORTED_LANGUAGES, Settings
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

    def test_static_assets_are_versioned_to_bypass_stale_service_worker_caches(self):
        base_template = (LOCALES_DIR.parent / "templates/base.html").read_text(encoding="utf-8")

        self.assertIn("filename='css/styles.css', v=app_version", base_template)
        self.assertIn("filename='js/app.js', v=app_version", base_template)

    def test_ui_uses_family_ledger_terminology_in_every_language(self):
        expected_by_language = {
            "en": {
                "family_wallet": "Family ledger",
                "children_wallets": "Children accounts",
                "available_balance": "Balance",
                "debt": "Negative balance",
                "overdraft_limit": "Minimum balance",
                "deposit": "Credit",
                "withdraw": "Debit",
                "transaction_details": "Entry details",
                "history": "Ledger history",
                "virtual_wallet": "Account",
            },
            "de": {
                "family_wallet": "Familien-Kassenbuch",
                "children_wallets": "Kinderkonten",
                "available_balance": "Kontostand",
                "debt": "Negativer Kontostand",
                "overdraft_limit": "Mindestkontostand",
                "deposit": "Gutschrift",
                "withdraw": "Sollbuchung",
                "transaction_details": "Buchungsdetails",
                "history": "Buchungsverlauf",
                "virtual_wallet": "Konto",
            },
            "it": {
                "family_wallet": "Registro familiare",
                "children_wallets": "Conti dei figli",
                "available_balance": "Saldo",
                "debt": "Saldo negativo",
                "overdraft_limit": "Saldo minimo",
                "deposit": "Accredito",
                "withdraw": "Addebito",
                "transaction_details": "Dettagli registrazione",
                "history": "Cronologia del registro",
                "virtual_wallet": "Conto",
            },
        }

        for language, expected in expected_by_language.items():
            catalog = json.loads((LOCALES_DIR / f"{language}.json").read_text(encoding="utf-8"))
            with self.subTest(language=language):
                self.assertEqual({key: catalog[key] for key in expected}, expected)

    def test_family_ledger_decision_documents_product_and_compatibility_boundaries(self):
        decision = (
            LOCALES_DIR.parent / "docs/decisions/0002-family-ledger-product-model.md"
        ).read_text(encoding="utf-8")

        for expected in (
            "positive: money is owed or credited to the child",
            "negative: money is owed by the child to the family",
            "### Preferred terminology",
            "### Compatibility boundary",
            "Preserve server-side parent/child account isolation",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, decision)


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
        self.assertIn(f"/static/js/app.js?v={PROJECT_VERSION}".encode(), response.data)
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
