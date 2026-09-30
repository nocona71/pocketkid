from __future__ import annotations

import os
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "pocketkid.db"
LOCALES_DIR = BASE_DIR / "locales"
VERSION_FILE = BASE_DIR / "VERSION"

SUPPORTED_LANGUAGES = ("en", "it", "de")
SUPPORTED_CURRENCIES = ("EUR", "USD", "GBP", "CHF")
CURRENCY_SYMBOLS = {
    "EUR": "€",
    "USD": "$",
    "GBP": "£",
    "CHF": "CHF",
}
DEFAULT_CURRENCY = "EUR"
DATE_FORMATS = {
    "DD/MM/YYYY": "%d/%m/%Y",
    "DD.MM.YYYY": "%d.%m.%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "YYYY-MM-DD": "%Y-%m-%d",
}
DEFAULT_DATE_FORMAT = "DD/MM/YYYY"
PROJECT_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()
APP_VERSION = PROJECT_VERSION
APP_CREDITS = os.getenv("APP_CREDITS", "Stefano Perna")
APP_REPO_URL = os.getenv("APP_REPO_URL", "https://github.com/nocona71/pocketkid")
APP_UPSTREAM_REPO_URL = os.getenv("APP_UPSTREAM_REPO_URL", "https://github.com/pernastefano/pocketkid")
APP_UPSTREAM_COMMIT = os.getenv("APP_UPSTREAM_COMMIT", "b0356f37956fe1f4d027bba68682591e590737b9")


class Settings:
    SECRET_KEY = os.getenv("SECRET_KEY", "pocketkid-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=int(os.getenv("SESSION_DAYS", "30")))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
