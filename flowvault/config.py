import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Config:
    """Application settings. Set FLASK_SECRET_KEY when deploying."""

    SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("FLASK_SECRET_KEY")
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    # Files always live on the host filesystem. FILE_STORAGE_DIR and
    # RECYCLE_BIN_DIR are the deployment-facing names; the older names remain
    # supported so existing installations do not need a data migration.
    FOLDER_ROOT = Path(
        os.getenv("FILE_STORAGE_DIR")
        or os.getenv("FOLDER_ROOT")
        or PROJECT_ROOT / "storage"
    ).resolve()
    STORAGE_PATH = Path(os.getenv("STORAGE_PATH") or FOLDER_ROOT).resolve()
    # Keep deleted items outside FOLDER_ROOT so they are never browsable as normal files.
    RECYCLE_BIN_PATH = Path(
        os.getenv("RECYCLE_BIN_DIR")
        or os.getenv("RECYCLE_BIN_PATH")
        or FOLDER_ROOT.parent / "recycle-bin"
    ).resolve()
    RECYCLE_BIN_RETENTION_DAYS = 15
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "db")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("MARIADB_ROOT_PASSWORD", "")
    ADMIN_EMAILS = {email.strip().lower() for email in os.getenv("ADMIN_EMAILS", "admin@flowvault.test").split(",")}
    OTP_TTL_SECONDS = 300
    OTP_RESEND_SECONDS = 60
    OTP_FAILURE_LIMIT = 5
    MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(64 * 1024 * 1024)))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_BYTES
    LOGIN_FAILURE_LIMIT = 3
    LOGIN_FAILURE_WINDOW_SECONDS = 60
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "1" if os.getenv("FLASK_ENV") == "production" else "0") == "1"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "0"))
