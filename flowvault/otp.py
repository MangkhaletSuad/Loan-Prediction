from __future__ import annotations

import base64
import hashlib
import secrets
import smtplib
from email.message import EmailMessage

from cryptography.fernet import Fernet
from flask import current_app

from flowvault.database import get_database_connection


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(current_app.config["SECRET_KEY"].encode()).digest())
    return Fernet(key)


def get_gmail_settings(include_password: bool = False) -> dict | None:
    with get_database_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT sender_email, smtp_host, smtp_port, use_tls, encrypted_app_password FROM otp_gmail_settings WHERE id = 1")
        settings = cursor.fetchone()
    if not settings:
        return None
    if include_password:
        settings["app_password"] = _fernet().decrypt(settings["encrypted_app_password"].encode()).decode()
    settings.pop("encrypted_app_password", None)
    return settings


def is_otp_enabled() -> bool:
    with get_database_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT enabled FROM otp_gmail_settings WHERE id = 1")
        settings = cursor.fetchone()
    # Secure default: OTP remains required until an administrator explicitly disables it.
    return settings is None or bool(settings["enabled"])


def save_gmail_settings(sender_email: str, app_password: str, smtp_host: str, smtp_port: int, use_tls: bool, enabled: bool) -> None:
    """Save OTP delivery settings while allowing an administrator to keep the current password."""
    if not 1 <= smtp_port <= 65535:
        raise ValueError("SMTP port must be between 1 and 65535")
    with get_database_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT encrypted_app_password FROM otp_gmail_settings WHERE id = 1")
        existing = cursor.fetchone()
        if not app_password and not existing:
            raise ValueError("An SMTP app password is required for the first OTP setup")
        encrypted_password = (
            _fernet().encrypt(app_password.encode()).decode()
            if app_password
            else existing["encrypted_app_password"]
        )
        cursor.execute("""INSERT INTO otp_gmail_settings (id, sender_email, encrypted_app_password, smtp_host, smtp_port, use_tls, enabled)
            VALUES (1, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE sender_email=VALUES(sender_email), encrypted_app_password=VALUES(encrypted_app_password),
            smtp_host=VALUES(smtp_host), smtp_port=VALUES(smtp_port), use_tls=VALUES(use_tls), enabled=VALUES(enabled), updated_at=CURRENT_TIMESTAMP""",
            (sender_email, encrypted_password, smtp_host, smtp_port, use_tls, enabled))
        connection.commit()


def create_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def send_otp(recipient: str, code: str) -> None:
    settings = get_gmail_settings(include_password=True)
    if not settings:
        raise RuntimeError("ผู้ดูแลระบบยังไม่ได้ตั้งค่า Gmail สำหรับ OTP")
    message = EmailMessage()
    message["Subject"] = "Landyhomehub login verification code"
    message["From"] = settings["sender_email"]
    message["To"] = recipient
    message.set_content(f"Your Landyhomehub verification code is: {code}\nThis code expires in 10 minutes.")
    with smtplib.SMTP(settings["smtp_host"], settings["smtp_port"], timeout=10) as smtp:
        if settings["use_tls"]:
            smtp.starttls()
        smtp.login(settings["sender_email"], settings["app_password"])
        smtp.send_message(message)
