from flask import request

from flowvault.database import get_database_connection


def record_event(email: str, action: str, detail: str | None = None) -> None:
    """Store an audit event without passwords, OTP values, or other secrets."""
    with get_database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO audit_logs (user_email, action, detail, ip_address) VALUES (%s, %s, %s, %s)",
            (email, action, detail, request.remote_addr),
        )
        connection.commit()
