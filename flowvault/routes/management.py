from functools import wraps

from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from flowvault.audit import record_event
from flowvault.database import get_database_connection

management_bp = Blueprint("management", __name__)

VALID_ROLES = {"user", "department_admin", "super_admin"}


def ensure_management_schema(cursor) -> None:
    """Add optional management fields without changing existing user records."""
    cursor.execute("SHOW COLUMNS FROM users LIKE 'permission_tier'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE users ADD COLUMN permission_tier VARCHAR(30) NULL")
    cursor.execute("SHOW TABLES LIKE 'file_shares'")
    if cursor.fetchone():
        cursor.execute("SHOW COLUMNS FROM file_shares LIKE 'expires_at'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE file_shares ADD COLUMN expires_at DATETIME NULL AFTER permission")
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS permission_tiers (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            tier_code VARCHAR(30) NOT NULL UNIQUE,
            description VARCHAR(255) NOT NULL,
            can_upload TINYINT(1) NOT NULL DEFAULT 0,
            can_manage TINYINT(1) NOT NULL DEFAULT 0,
            can_share TINYINT(1) NOT NULL DEFAULT 0,
            enabled TINYINT(1) NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    cursor.execute("SELECT COUNT(*) AS total FROM permission_tiers")
    if cursor.fetchone()["total"] == 0:
        cursor.executemany(
            "INSERT INTO permission_tiers (tier_code, description, can_upload, can_manage, can_share) VALUES (%s, %s, %s, %s, %s)",
            [
                ("T1", "View and download only", 0, 0, 0),
                ("T2", "View, download and upload", 1, 0, 0),
                ("T3", "Full file management", 1, 1, 1),
            ],
        )


def require_roles(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_email" not in session:
                return redirect(url_for("auth.login"))
            with get_database_connection() as connection, connection.cursor() as cursor:
                cursor.execute("SELECT id, email, role, department FROM users WHERE id=%s AND email=%s", (session.get("user_id"), session.get("user_email")))
                current_user = cursor.fetchone()
            if not current_user or current_user["role"] not in roles:
                flash("คุณไม่มีสิทธิ์เข้าถึงเมนูนี้")
                return redirect(url_for("files.my_files"))
            session.update(user_id=current_user["id"], user_role=current_user["role"], user_department=current_user["department"])
            return view(*args, **kwargs)
        return wrapped
    return decorator


@management_bp.get("/shared-with-me")
@require_roles("user", "department_admin", "super_admin")
def shared_with_me():
    email = request.args.get("email", "").strip().lower()
    with get_database_connection() as connection, connection.cursor() as cursor:
        ensure_management_schema(cursor)
        connection.commit()
        if email:
            cursor.execute("SELECT item_name, permission, shared_by, recipient_email, created_at, expires_at, expires_at > UTC_TIMESTAMP() AS is_active FROM file_shares WHERE recipient_email=%s AND (shared_by LIKE %s OR recipient_email LIKE %s) ORDER BY created_at DESC", (session["user_email"], f"%{email}%", f"%{email}%"))
        else:
            cursor.execute("SELECT item_name, permission, shared_by, recipient_email, created_at, expires_at, expires_at > UTC_TIMESTAMP() AS is_active FROM file_shares WHERE recipient_email=%s ORDER BY created_at DESC", (session["user_email"],))
        shares = cursor.fetchall()
    preview_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
    for share in shares:
        share["can_preview"] = Path(share["item_name"]).suffix.lower() in preview_extensions
    return render_template("management/shared.html", shares=shares, selected_email=email)


@management_bp.route("/admin/users", methods=["GET", "POST"])
@require_roles("department_admin", "super_admin")
def users_permissions():
    is_super_admin = session.get("user_role") == "super_admin"
    current_department = session.get("user_department")
    with get_database_connection() as connection, connection.cursor() as cursor:
        ensure_management_schema(cursor)
        connection.commit()
    if request.method == "POST":
        action = request.form.get("action", "update")
        role = request.form.get("role", "user")
        department = request.form.get("department", "").strip() or None
        tier = request.form.get("permission_tier", "").strip() or None
        if not is_super_admin:
            if action != "add" or not current_department:
                flash("คุณมีสิทธิ์เพิ่มผู้ใช้เฉพาะในฝ่ายของตนเอง")
                return redirect(url_for("management.users_permissions"))
            role = "user"
            department = current_department
            tier = None
        if action == "add":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not email or "@" not in email or len(password) < 8 or role not in VALID_ROLES:
                flash("ระบุอีเมลที่ถูกต้องและรหัสผ่านอย่างน้อย 8 ตัวอักษร")
            else:
                with get_database_connection() as connection, connection.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM departments WHERE name=%s", (department,))
                    if not cursor.fetchone():
                        flash("กรุณาเลือกฝ่ายที่มีอยู่ในระบบ")
                        return redirect(url_for("management.users_permissions"))
                    cursor.execute("SELECT 1 FROM users WHERE email=%s", (email,))
                    if cursor.fetchone():
                        flash("อีเมลนี้มีผู้ใช้งานแล้ว")
                        return redirect(url_for("management.users_permissions"))
                    cursor.execute("INSERT INTO users (email, password_hash, role, department, permission_tier) VALUES (%s, %s, %s, %s, %s)", (email, generate_password_hash(password), role, department, tier))
                    connection.commit()
                record_event(session["user_email"], "user_created", email)
                flash("เพิ่มผู้ใช้แล้ว")
        elif action == "delete":
            if request.form.get("user_id") == str(session.get("user_id", "")):
                flash("ไม่สามารถลบบัญชีที่กำลังใช้งานอยู่")
            else:
                with get_database_connection() as connection, connection.cursor() as cursor:
                    cursor.execute("DELETE FROM users WHERE id=%s AND email<>%s", (request.form.get("user_id"), session["user_email"]))
                    connection.commit()
                record_event(session["user_email"], "user_deleted", f"user_id={request.form.get('user_id')}")
                flash("ลบผู้ใช้แล้ว")
        elif role in VALID_ROLES:
            with get_database_connection() as connection, connection.cursor() as cursor:
                cursor.execute("UPDATE users SET role=%s, department=%s, permission_tier=%s WHERE id=%s", (role, department, tier, request.form["user_id"]))
                connection.commit()
            record_event(session["user_email"], "user_permissions_updated", f"user_id={request.form['user_id']}")
            flash("อัปเดตสิทธิ์ผู้ใช้แล้ว")
    with get_database_connection() as connection, connection.cursor() as cursor:
        ensure_management_schema(cursor)
        if is_super_admin:
            cursor.execute("SELECT id, email, role, department, permission_tier, created_at FROM users ORDER BY email")
        else:
            cursor.execute("SELECT id, email, role, department, permission_tier, created_at FROM users WHERE department=%s ORDER BY email", (current_department,))
        users = cursor.fetchall()
        if is_super_admin:
            cursor.execute("SELECT name FROM departments ORDER BY name")
            departments = cursor.fetchall()
        else:
            departments = [{"name": current_department}] if current_department else []
        cursor.execute("SELECT tier_code, description FROM permission_tiers WHERE enabled=1 ORDER BY tier_code")
        tiers = cursor.fetchall()
    return render_template("management/users.html", users=users, departments=departments, tiers=tiers, is_super_admin=is_super_admin, current_department=current_department)


@management_bp.get("/admin/usage/<kind>")
@require_roles("department_admin", "super_admin")
def usage(kind: str):
    if kind not in {"download", "upload"}:
        return redirect(url_for("files.my_files"))
    period = request.args.get("period", "day")
    days = {"day": 1, "week": 7, "month": 30}.get(period, 1)
    since = datetime.now() - timedelta(days=days)
    action = f"{kind}_%"
    with get_database_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT user_email, COUNT(*) AS total, MAX(created_at) AS last_used FROM audit_logs WHERE action LIKE %s AND created_at >= %s GROUP BY user_email ORDER BY total DESC", (action, since))
        rows = cursor.fetchall()
        if period == "day":
            bucket = "%H:00"
            group_by = "DATE(created_at), HOUR(created_at)"
        elif period == "week":
            bucket = "%a %d %b"
            group_by = "DATE(created_at)"
        else:
            bucket = "%d %b"
            group_by = "DATE(created_at)"
        cursor.execute(
            "SELECT DATE_FORMAT(created_at, %s) AS label, COUNT(*) AS total "
            "FROM audit_logs WHERE action LIKE %s AND created_at >= %s "
            f"GROUP BY {group_by} "
            "ORDER BY MIN(created_at)",
            (bucket, action, since),
        )
        chart_rows = cursor.fetchall()
    # Audit records currently track actions, not byte sizes.  Keep the time axis
    # complete so the volume chart remains useful and visually stable before the
    # first measured transfer is recorded.
    now = datetime.now()
    if period == "day":
        chart_labels = [(now - timedelta(hours=offset)).strftime("%H:00") for offset in range(23, -1, -1)]
    elif period == "week":
        chart_labels = [(now - timedelta(days=offset)).strftime("%a %d") for offset in range(6, -1, -1)]
    else:
        chart_labels = [(now - timedelta(days=offset)).strftime("%d %b") for offset in range(29, -1, -1)]
    return render_template(
        "management/usage.html",
        kind=kind.title(),
        rows=rows,
        period=period,
        total_events=sum(row["total"] for row in rows),
        active_users=len(rows),
        chart_labels=chart_labels,
        chart_values=[],
    )


@management_bp.route("/admin/file-types", methods=["GET", "POST"])
@require_roles("department_admin", "super_admin")
def file_types():
    if request.method == "POST":
        action = request.form.get("action", "add")
        extension = request.form.get("extension", "").strip().lower().lstrip(".")
        if action == "toggle":
            with get_database_connection() as connection, connection.cursor() as cursor:
                cursor.execute("UPDATE allowed_file_types SET enabled=%s WHERE id=%s", (1 if request.form.get("enabled") else 0, request.form.get("type_id")))
                connection.commit()
            record_event(session["user_email"], "file_type_toggled", f"type_id={request.form.get('type_id')}")
        elif action == "delete":
            with get_database_connection() as connection, connection.cursor() as cursor:
                cursor.execute("DELETE FROM allowed_file_types WHERE id=%s", (request.form.get("type_id"),))
                connection.commit()
            record_event(session["user_email"], "file_type_deleted", f"type_id={request.form.get('type_id')}")
            flash("ลบประเภทไฟล์แล้ว")
        elif extension.replace("-", "").isalnum():
            extensions = {item.strip().lower().lstrip(".") for item in extension.replace("\n", ",").split(",")}
            with get_database_connection() as connection, connection.cursor() as cursor:
                cursor.executemany("INSERT IGNORE INTO allowed_file_types (extension) VALUES (%s)", [(item,) for item in extensions if item and item.replace("-", "").isalnum()])
                connection.commit()
            record_event(session["user_email"], "file_types_added", ", ".join(sorted(extensions))[:255])
            flash("บันทึกประเภทไฟล์แล้ว")
    with get_database_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id, extension, enabled FROM allowed_file_types ORDER BY extension")
        types = cursor.fetchall()
    return render_template("management/file_types.html", types=types)


@management_bp.route("/admin/departments", methods=["GET", "POST"])
@require_roles("super_admin")
def departments():
    if request.method == "POST":
        action = request.form.get("action", "add")
        name = request.form.get("name", "").strip()
        if action == "delete":
            with get_database_connection() as connection, connection.cursor() as cursor:
                cursor.execute("UPDATE users SET department=NULL WHERE department=(SELECT name FROM departments WHERE id=%s)", (request.form.get("department_id"),))
                cursor.execute("DELETE FROM departments WHERE id=%s", (request.form.get("department_id"),))
                connection.commit()
            record_event(session["user_email"], "department_deleted", f"department_id={request.form.get('department_id')}")
            flash("ลบฝ่ายแล้ว")
        elif name:
            with get_database_connection() as connection, connection.cursor() as cursor:
                cursor.execute("INSERT IGNORE INTO departments (name) VALUES (%s)", (name,))
                connection.commit()
            record_event(session["user_email"], "department_created", name)
            flash("เพิ่มฝ่ายแล้ว")
    with get_database_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT d.id, d.name, d.created_at, COUNT(u.id) AS members, GROUP_CONCAT(CASE WHEN u.role='department_admin' THEN u.email END SEPARATOR ', ') AS admins FROM departments d LEFT JOIN users u ON BINARY u.department=BINARY d.name GROUP BY d.id, d.name, d.created_at ORDER BY d.name")
        departments = cursor.fetchall()
    return render_template("management/departments.html", departments=departments)


@management_bp.route("/admin/permission-tiers", methods=["GET", "POST"])
@require_roles("super_admin")
def permission_tiers():
    if request.method == "POST":
        action = request.form.get("action", "save")
        with get_database_connection() as connection, connection.cursor() as cursor:
            ensure_management_schema(cursor)
            if action == "add":
                cursor.execute("INSERT INTO permission_tiers (tier_code, description) VALUES (%s, %s)", (request.form.get("tier_code", "").strip().upper(), request.form.get("description", "").strip()))
            elif action == "delete":
                cursor.execute("DELETE FROM permission_tiers WHERE id=%s", (request.form.get("tier_id"),))
            else:
                cursor.execute("UPDATE permission_tiers SET tier_code=%s, description=%s, can_upload=%s, can_manage=%s, can_share=%s, enabled=%s WHERE id=%s", (request.form.get("tier_code", "").strip().upper(), request.form.get("description", "").strip(), 1 if request.form.get("can_upload") else 0, 1 if request.form.get("can_manage") else 0, 1 if request.form.get("can_share") else 0, 1 if request.form.get("enabled") else 0, request.form.get("tier_id")))
            connection.commit()
        record_event(session["user_email"], f"permission_tier_{action}", request.form.get("tier_code", "")[:255])
        flash("บันทึก Permission Tier แล้ว")
    with get_database_connection() as connection, connection.cursor() as cursor:
        ensure_management_schema(cursor)
        cursor.execute("SELECT t.*, COUNT(u.id) AS users FROM permission_tiers t LEFT JOIN users u ON BINARY u.permission_tier=BINARY t.tier_code GROUP BY t.id ORDER BY t.tier_code")
        tiers = cursor.fetchall()
    return render_template("management/permission_tiers.html", tiers=tiers)
