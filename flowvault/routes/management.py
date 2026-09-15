from functools import wraps

from datetime import datetime, timedelta
from pathlib import Path
import re

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from flowvault.audit import record_event
from flowvault.database import get_database_connection

management_bp = Blueprint("management", __name__)

VALID_ROLES = {"user", "department_admin", "super_admin"}
TIER_DEFINITIONS = {
    "T1": ("Full file access — Preview, Download, Create, Upload, Share, Rename, Move, Overwrite, Delete", 1, 1, 1, 1, 1),
    "T2": ("Create and modify, no delete — Preview, Download, Create, Upload, Share, Rename, Move, Overwrite", 1, 1, 1, 1, 0),
    "T3": ("Preview and download — Preview, Download", 1, 1, 0, 0, 0),
    "T4": ("Preview only — Preview", 1, 0, 0, 0, 0),
}


def _tier_is_assignable(cursor, tier_code: str) -> bool:
    cursor.execute("SELECT 1 FROM permission_tiers WHERE tier_code=%s AND enabled=1", (tier_code,))
    return cursor.fetchone() is not None


def _tier_rights_from_form() -> tuple[int, int, int, int, int]:
    return tuple(int(request.form.get(field) == "on") for field in (
        "can_preview", "can_download", "can_create", "can_modify", "can_delete",
    ))


def _tier_rights_description(rights: tuple[int, int, int, int, int]) -> str:
    labels = ("Preview", "Download", "Create / share", "Modify / overwrite", "Delete")
    selected = [label for label, allowed in zip(labels, rights) if allowed]
    return ", ".join(selected) if selected else "No file permissions"


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
        cursor.execute("SHOW COLUMNS FROM file_shares LIKE 'storage_root'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE file_shares ADD COLUMN storage_root VARCHAR(1024) NULL AFTER item_name")
            # Preserve the scope at migration time for existing shares. New shares always store it explicitly.
            cursor.execute(
                "UPDATE file_shares AS s LEFT JOIN users AS u ON u.email=s.shared_by "
                "SET s.storage_root=CASE WHEN u.role='super_admin' THEN '' "
                "WHEN u.department IS NOT NULL THEN u.department ELSE u.email END"
            )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS permission_tiers (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            tier_code VARCHAR(30) NOT NULL UNIQUE,
            description VARCHAR(255) NOT NULL,
            can_preview TINYINT(1) NOT NULL DEFAULT 0,
            can_download TINYINT(1) NOT NULL DEFAULT 0,
            can_create TINYINT(1) NOT NULL DEFAULT 0,
            can_modify TINYINT(1) NOT NULL DEFAULT 0,
            can_delete TINYINT(1) NOT NULL DEFAULT 0,
            enabled TINYINT(1) NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    for column in ("can_preview", "can_download", "can_create", "can_modify", "can_delete"):
        cursor.execute(f"SHOW COLUMNS FROM permission_tiers LIKE '{column}'")
        if not cursor.fetchone():
            cursor.execute(f"ALTER TABLE permission_tiers ADD COLUMN {column} TINYINT(1) NOT NULL DEFAULT 0")
    cursor.executemany(
        """INSERT INTO permission_tiers
           (tier_code, description, can_preview, can_download, can_create, can_modify, can_delete, enabled)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
           ON DUPLICATE KEY UPDATE tier_code=VALUES(tier_code)""",
        [(code, *definition) for code, definition in TIER_DEFINITIONS.items()],
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS recycle_bin_items (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            item_type VARCHAR(10) NOT NULL,
            storage_root VARCHAR(1024) NOT NULL,
            original_path VARCHAR(1024) NOT NULL,
            trash_token CHAR(32) NOT NULL UNIQUE,
            deleted_by VARCHAR(254) NOT NULL,
            deleted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            INDEX idx_recycle_bin_scope_expiry (storage_root(255), expires_at)
        )"""
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
        tier = request.form.get("permission_tier", "").strip()
        if not is_super_admin:
            if action != "add" or not current_department:
                flash("คุณมีสิทธิ์เพิ่มผู้ใช้เฉพาะในฝ่ายของตนเอง")
                return redirect(url_for("management.users_permissions"))
            role = "user"
            department = current_department
        if action == "add":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not email or "@" not in email or len(password) < 8 or role not in VALID_ROLES:
                flash("ระบุอีเมลที่ถูกต้องและรหัสผ่านอย่างน้อย 8 ตัวอักษร")
            else:
                with get_database_connection() as connection, connection.cursor() as cursor:
                    if not _tier_is_assignable(cursor, tier):
                        flash("Permission Tier ไม่ถูกต้องหรือถูกปิดใช้งาน")
                        return redirect(url_for("management.users_permissions"))
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
                if not _tier_is_assignable(cursor, tier):
                    flash("Permission Tier ไม่ถูกต้องหรือถูกปิดใช้งาน")
                    return redirect(url_for("management.users_permissions"))
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
        cursor.execute("SELECT tier_code, description FROM permission_tiers WHERE enabled=1 ORDER BY CAST(SUBSTRING(tier_code, 2) AS UNSIGNED), tier_code")
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
        rights = _tier_rights_from_form()
        description = request.form.get("description", "").strip()[:255] or _tier_rights_description(rights)
        with get_database_connection() as connection, connection.cursor() as cursor:
            ensure_management_schema(cursor)
            if action == "create":
                tier_code = request.form.get("tier_code", "").strip().upper()
                if not re.fullmatch(r"T[1-9][0-9]*", tier_code):
                    flash("รหัส Custom Tier ต้องเป็น T ตามด้วยตัวเลข เช่น T5 หรือ T6")
                    return redirect(url_for("management.permission_tiers"))
                cursor.execute(
                    "INSERT INTO permission_tiers (tier_code, description, can_preview, can_download, can_create, can_modify, can_delete) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (tier_code, description, *rights),
                )
                record_event(session["user_email"], "permission_tier_created", tier_code)
                flash(f"สร้าง Permission Tier {tier_code} แล้ว")
            elif action == "delete" and request.form.get("tier_id", "").isdigit():
                cursor.execute("SELECT tier_code FROM permission_tiers WHERE id=%s", (request.form["tier_id"],))
                tier = cursor.fetchone()
                tier_match = re.fullmatch(r"T([1-9][0-9]*)", tier["tier_code"] if tier else "")
                if not tier_match or int(tier_match.group(1)) < 5:
                    flash("ลบได้เฉพาะ Custom Tier ตั้งแต่ T5 ขึ้นไป")
                else:
                    cursor.execute("SELECT COUNT(*) AS users FROM users WHERE permission_tier=%s", (tier["tier_code"],))
                    if cursor.fetchone()["users"]:
                        flash(f"ไม่สามารถลบ {tier['tier_code']} ได้ เพราะยังมีผู้ใช้กำหนด Tier นี้อยู่")
                    else:
                        cursor.execute("DELETE FROM permission_tiers WHERE id=%s", (request.form["tier_id"],))
                        record_event(session["user_email"], "permission_tier_deleted", tier["tier_code"])
                        flash(f"ลบ Permission Tier {tier['tier_code']} แล้ว")
            elif action == "save" and request.form.get("tier_id", "").isdigit():
                cursor.execute(
                    "UPDATE permission_tiers SET description=%s, can_preview=%s, can_download=%s, can_create=%s, can_modify=%s, can_delete=%s WHERE id=%s",
                    (description, *rights, request.form["tier_id"]),
                )
                if cursor.rowcount:
                    record_event(session["user_email"], "permission_tier_saved", f"tier_id={request.form['tier_id']}")
                    flash("บันทึก Permission Tier แล้ว")
                else:
                    flash("ไม่พบ Permission Tier ที่ต้องการบันทึก")
            else:
                flash("ข้อมูล Permission Tier ไม่ถูกต้อง")
            connection.commit()
        return redirect(url_for("management.permission_tiers"))
    with get_database_connection() as connection, connection.cursor() as cursor:
        ensure_management_schema(cursor)
        connection.commit()
        cursor.execute("SELECT t.*, COUNT(u.id) AS users FROM permission_tiers t LEFT JOIN users u ON BINARY u.permission_tier=BINARY t.tier_code GROUP BY t.id ORDER BY CAST(SUBSTRING(t.tier_code, 2) AS UNSIGNED), t.tier_code")
        tiers = cursor.fetchall()
    return render_template("management/permission_tiers.html", tiers=tiers)
