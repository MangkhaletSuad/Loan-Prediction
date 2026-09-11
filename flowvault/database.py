from __future__ import annotations

from typing import Any

import pymysql
from flask import current_app
from pymysql.connections import Connection


def get_database_connection() -> Connection:
    """Open a MariaDB connection using the environment-backed Flask config."""
    return pymysql.connect(
        host=current_app.config["DB_HOST"],
        port=current_app.config["DB_PORT"],
        user=current_app.config["DB_USER"],
        password=current_app.config["DB_PASSWORD"],
        database=current_app.config["DB_NAME"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10,
        autocommit=False,
    )


def check_database_connection() -> dict[str, Any]:
    """Return a safe health-check result without exposing connection secrets."""
    with get_database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 AS connected")
            return cursor.fetchone()
