import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

class Config:
    """Application settings. Set FLASK_SECRET_KEY when deploying."""

    SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("FLASK_SECRET_KEY")
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    # Point STORAGE_PATH at the volume or folder that stores uploaded files.
    STORAGE_PATH = Path(os.getenv("STORAGE_PATH", Path(__file__).resolve().parent.parent))
    FOLDER_ROOT = Path(os.getenv("FOLDER_ROOT", STORAGE_PATH / "storage")).resolve()
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "db")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("MARIADB_ROOT_PASSWORD", "")
    ADMIN_EMAILS = {email.strip().lower() for email in os.getenv("ADMIN_EMAILS", "admin@flowvault.test").split(",")}
    OTP_TTL_SECONDS = 300
    OTP_RESEND_SECONDS = 60
    LOGIN_FAILURE_LIMIT = 3
    LOGIN_FAILURE_WINDOW_SECONDS = 60
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "1" if os.getenv("FLASK_ENV") == "production" else "0") == "1"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
