from datetime import datetime, timedelta, timezone
import mimetypes
from pathlib import Path
import re
from shutil import disk_usage

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for, flash, send_file
from flowvault.audit import record_event
from flowvault.database import get_database_connection
from flowvault.routes.management import ensure_management_schema

files_bp = Blueprint("files", __name__, url_prefix="/my-files")
MAX_DIRECTORY_ENTRIES = 1000
MAX_SHARE_RECIPIENTS = 20
MAX_SHARE_FILES = 100
SHARE_EXPIRY_DAYS = {1, 7, 30, 90}


def build_disk_tree(root: Path, current: Path | None = None) -> list[dict]:
    current = current or root
    if not current.is_dir():
        return []
    nodes = []
    for entry in sorted(current.iterdir(), key=lambda item: item.name.casefold())[:MAX_DIRECTORY_ENTRIES]:
        if entry.is_dir() and not entry.is_symlink():
            nodes.append({"name": entry.name, "relative_path": entry.relative_to(root).as_posix(), "children": build_disk_tree(root, entry)})
    return nodes


def selected_directory(root: Path, requested_path: str) -> Path:
    candidate = (root / requested_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return root
    return candidate if candidate.is_dir() else root


def directory_size(directory: Path) -> int:
    total = 0
    for item in directory.rglob("*"):
        if item.is_symlink():
            continue
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def format_size(size_bytes: int) -> str:
    return f"{size_bytes / 1024:.2f} KB"


def format_created_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_ctime).strftime("%d %b %Y, %H:%M")


def _safe_file_path(folder_root: Path, relative_path: str) -> Path | None:
    candidate = (folder_root / relative_path).resolve()
    try:
        candidate.relative_to(folder_root.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _current_user_can_share() -> bool:
    """Return whether the current authenticated user may create file shares."""
    if session.get("user_role") == "super_admin":
        return True
    with get_database_connection() as connection, connection.cursor() as cursor:
        ensure_management_schema(cursor)
        cursor.execute(
            """SELECT t.can_share
               FROM users AS u
               LEFT JOIN permission_tiers AS t
                 ON t.tier_code = u.permission_tier AND t.enabled = 1
               WHERE u.id=%s AND u.email=%s""",
            (session.get("user_id"), session.get("user_email")),
        )
        row = cursor.fetchone()
        connection.commit()
    return bool(row and row["can_share"])


@files_bp.post("/share")
def share_file():
    if "user_email" not in session:
        return redirect(url_for("auth.login"))
    if not _current_user_can_share():
        flash("คุณไม่มีสิทธิ์แชร์ไฟล์ โปรดติดต่อผู้ดูแลระบบ")
        return redirect(url_for("files.my_files"))
    recipients_input = request.form.get("recipient_emails", request.form.get("recipient_email", ""))
    recipients = list(dict.fromkeys(email.strip().lower() for email in re.split(r"[,;\n]+", recipients_input) if email.strip()))
    relative_paths = list(dict.fromkeys(path.strip() for path in request.form.getlist("file_paths") if path.strip()))
    if not relative_paths and request.form.get("file_path", "").strip():
        relative_paths = [request.form["file_path"].strip()]
    permission = request.form.get("permission", "view").strip().lower()
    try:
        expiry_days = int(request.form.get("expires_in_days", ""))
    except ValueError:
        expiry_days = 0
    if (
        permission not in {"view", "download"}
        or not recipients
        or len(recipients) > MAX_SHARE_RECIPIENTS
        or expiry_days not in SHARE_EXPIRY_DAYS
        or any(len(email) > 254 or "@" not in email or email == session["user_email"] for email in recipients)
        or not relative_paths
        or len(relative_paths) > MAX_SHARE_FILES
        or any(len(path) > 1024 or "\x00" in path or Path(path).is_absolute() for path in relative_paths)
    ):
        flash("ข้อมูลการแชร์ไม่ถูกต้อง")
        return redirect(url_for("files.my_files"))
    root = Path(current_app.config["FOLDER_ROOT"])
    if session.get("user_role") != "super_admin":
        root = root / (session.get("user_department") or session["user_email"])
    if not all(_safe_file_path(root, relative_path) for relative_path in relative_paths):
        flash("ไม่พบไฟล์บางรายการหรือคุณไม่มีสิทธิ์แชร์")
        return redirect(url_for("files.my_files"))
    with get_database_connection() as connection, connection.cursor() as cursor:
        ensure_management_schema(cursor)
        placeholders = ", ".join(["%s"] * len(recipients))
        cursor.execute(f"SELECT email FROM users WHERE email IN ({placeholders})", recipients)
        found_recipients = {row["email"].lower() for row in cursor.fetchall()}
        if found_recipients != set(recipients):
            flash("ไม่พบผู้ใช้จากอีเมลที่ระบุ")
            return redirect(url_for("files.my_files"))
        for relative_path in relative_paths:
            for recipient in recipients:
                cursor.execute(
                    "SELECT 1 FROM file_shares WHERE item_name=%s AND shared_by=%s AND recipient_email=%s LIMIT 1",
                    (relative_path, session["user_email"], recipient),
                )
                if cursor.fetchone():
                    cursor.execute(
                        f"UPDATE file_shares SET permission=%s, expires_at=DATE_ADD(UTC_TIMESTAMP(), INTERVAL {expiry_days} DAY) WHERE item_name=%s AND shared_by=%s AND recipient_email=%s",
                        (permission, relative_path, session["user_email"], recipient),
                    )
                else:
                    cursor.execute(
                        f"INSERT INTO file_shares (item_name, permission, expires_at, shared_by, recipient_email) VALUES (%s, %s, DATE_ADD(UTC_TIMESTAMP(), INTERVAL {expiry_days} DAY), %s, %s)",
                        (relative_path, permission, session["user_email"], recipient),
                    )
        connection.commit()
    record_event(session["user_email"], "file_shared", f"{len(relative_paths)} file(s) -> {len(recipients)} recipient(s), expires in {expiry_days} days")
    flash(f"แชร์ {len(relative_paths)} ไฟล์ให้ {len(recipients)} คนเรียบร้อยแล้ว")
    return redirect(url_for("files.my_files"))


@files_bp.get("/share-recipients")
def share_recipients():
    if "user_email" not in session:
        return jsonify([]), 401
    if not _current_user_can_share():
        return jsonify([]), 403
    query = request.args.get("q", "").strip().lower()
    if len(query) < 2:
        return jsonify([])
    with get_database_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT email FROM users WHERE email LIKE %s AND email<>%s ORDER BY email LIMIT 10", (f"%{query}%", session["user_email"]))
        return jsonify([row["email"] for row in cursor.fetchall()])


@files_bp.get("/preview")
def preview_file():
    """Preview an image or PDF inside the current user's permitted folder."""
    if "user_email" not in session:
        return redirect(url_for("auth.login"))
    relative_path = request.args.get("file", "").strip()
    root = Path(current_app.config["FOLDER_ROOT"])
    if session.get("user_role") != "super_admin":
        root = root / (session.get("user_department") or session["user_email"])
    file_path = _safe_file_path(root, relative_path)
    mime_type, _ = mimetypes.guess_type(file_path.name if file_path else "")
    if not file_path or not (mime_type == "application/pdf" or (mime_type and mime_type.startswith("image/"))):
        return "Not found", 404
    return send_file(file_path, mimetype=mime_type, as_attachment=False, conditional=True)


@files_bp.get("/shared-preview")
def shared_preview():
    if "user_email" not in session:
        return redirect(url_for("auth.login"))
    owner = request.args.get("owner", "").strip().lower()
    relative_path = request.args.get("file", "").strip()
    with get_database_connection() as connection, connection.cursor() as cursor:
        ensure_management_schema(cursor)
        connection.commit()
        cursor.execute("SELECT permission FROM file_shares WHERE recipient_email=%s AND shared_by=%s AND item_name=%s AND expires_at > UTC_TIMESTAMP() LIMIT 1", (session["user_email"], owner, relative_path))
        allowed = cursor.fetchone()
        cursor.execute("SELECT department, role FROM users WHERE email=%s", (owner,))
        owner_row = cursor.fetchone()
    if not allowed or allowed["permission"] not in {"view", "download"} or not owner_row:
        return "Not found", 404
    root = Path(current_app.config["FOLDER_ROOT"])
    if owner_row["role"] != "super_admin":
        root = root / (owner_row["department"] or owner)
    file_path = _safe_file_path(root, relative_path)
    mime_type, _ = mimetypes.guess_type(file_path.name if file_path else "")
    if not file_path or not (mime_type == "application/pdf" or (mime_type and mime_type.startswith("image/"))):
        return "Not found", 404
    record_event(session["user_email"], "shared_file_previewed", f"{owner}:{relative_path}")
    return send_file(file_path, mimetype=mime_type, as_attachment=False, conditional=True)


@files_bp.get("/shared-download")
def shared_download():
    if "user_email" not in session:
        return redirect(url_for("auth.login"))
    owner = request.args.get("owner", "").strip().lower()
    relative_path = request.args.get("file", "").strip()
    with get_database_connection() as connection, connection.cursor() as cursor:
        ensure_management_schema(cursor)
        connection.commit()
        cursor.execute("SELECT permission FROM file_shares WHERE recipient_email=%s AND shared_by=%s AND item_name=%s AND expires_at > UTC_TIMESTAMP() LIMIT 1", (session["user_email"], owner, relative_path))
        allowed = cursor.fetchone()
        cursor.execute("SELECT department, role FROM users WHERE email=%s", (owner,))
        owner_row = cursor.fetchone()
    if not allowed or allowed["permission"] != "download" or not owner_row:
        return "Not found", 404
    root = Path(current_app.config["FOLDER_ROOT"])
    if owner_row["role"] != "super_admin":
        root = root / (owner_row["department"] or owner)
    file_path = _safe_file_path(root, relative_path)
    if not file_path:
        return "Not found", 404
    record_event(session["user_email"], "shared_file_downloaded", f"{owner}:{relative_path}")
    return send_file(file_path, as_attachment=True, download_name=file_path.name)


@files_bp.get("")
@files_bp.get("/")
def my_files():
    if "user_email" not in session:
        return redirect(url_for("auth.login"))
    # Thailand uses ICT (UTC+7) year-round and does not observe daylight saving time.
    current_time = datetime.now(timezone(timedelta(hours=7), name="ICT"))
    display_date = (
        current_time.strftime("%A, ")
        + str(current_time.day)
        + current_time.strftime(" %B %Y, %H:%M")
    )
    storage = disk_usage(current_app.config["STORAGE_PATH"])
    used_gb = storage.used / (1024**3)
    total_gb = storage.total / (1024**3)
    storage_summary = {
        "used": f"{used_gb:.1f}",
        "total": f"{total_gb:.1f}",
        "percent_used": round((storage.used / storage.total) * 100),
    }
    folder_root = Path(current_app.config["FOLDER_ROOT"])
    if session.get("user_role") != "super_admin":
        scope = session.get("user_department") or session.get("user_email", "")
        folder_root = folder_root / scope
    folder_root.mkdir(parents=True, exist_ok=True)
    folder_tree = build_disk_tree(folder_root)
    active_directory = selected_directory(folder_root, request.args.get("folder", ""))
    entries = sorted(active_directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold()))[:MAX_DIRECTORY_ENTRIES]
    browser = {
        "name": "storage" if active_directory == folder_root else active_directory.name,
        "relative_path": "" if active_directory == folder_root else active_directory.relative_to(folder_root).as_posix(),
        "folder_count": sum(item.is_dir() for item in entries),
        "file_count": sum(item.is_file() for item in entries),
        "size": format_size(directory_size(active_directory)),
        "folders": [{"name": item.name, "relative_path": item.relative_to(folder_root).as_posix(), "size": format_size(directory_size(item)), "created_at": format_created_at(item), "created_by": "System Admin"} for item in entries if item.is_dir()],
                "files": [{"name": item.name, "relative_path": item.relative_to(folder_root).as_posix(), "size": format_size(item.stat().st_size), "created_at": format_created_at(item), "created_by": "System Admin"} for item in entries if item.is_file()],
    }
    return render_template(
        "files/my_files.html",
        today=display_date,
        user_email=session["user_email"],
        user_role=session.get("user_role", "user"),
        is_super_admin=session.get("user_role") == "super_admin",
        is_department_admin=session.get("user_role") == "department_admin",
        storage=storage_summary,
        folder_tree=folder_tree,
        browser=browser,
    )
