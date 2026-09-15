from datetime import datetime, timedelta, timezone
from io import BytesIO
import mimetypes
import os
from pathlib import Path
import re
from shutil import disk_usage, rmtree
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for, flash, send_file
from pymysql import MySQLError
from flowvault.audit import record_event
from flowvault.database import get_database_connection
from flowvault.routes.management import ensure_management_schema

files_bp = Blueprint("files", __name__, url_prefix="/my-files")
MAX_DIRECTORY_ENTRIES = 1000
MAX_SHARE_RECIPIENTS = 20
MAX_SHARE_FILES = 100
SHARE_EXPIRY_DAYS = {1, 7, 30, 90}
MAX_MANAGED_FILES = 100
PREVIEW_MIME_TYPES = {
    "application/pdf",
    "image/bmp",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
}


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


def _safe_directory_path(folder_root: Path, relative_path: str) -> Path | None:
    candidate = (folder_root / relative_path).resolve()
    try:
        candidate.relative_to(folder_root.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_dir() else None


def _current_user_permissions() -> dict[str, bool] | None:
    """Refresh the file principal from the database and return its permissions."""
    with get_database_connection() as connection, connection.cursor() as cursor:
        ensure_management_schema(cursor)
        cursor.execute(
            """SELECT u.id, u.email, u.role, u.department,
                      t.can_preview, t.can_download, t.can_create, t.can_modify, t.can_delete
               FROM users AS u
               LEFT JOIN permission_tiers AS t
                 ON BINARY t.tier_code = BINARY u.permission_tier AND t.enabled = 1
               WHERE u.id=%s AND u.email=%s""",
            (session.get("user_id"), session.get("user_email")),
        )
        row = cursor.fetchone()
        connection.commit()
    if not row:
        session.clear()
        return None
    session.update(
        user_id=row["id"],
        user_email=row["email"],
        user_role=row["role"],
        user_department=row["department"],
    )
    if row["role"] == "super_admin":
        return {"can_preview": True, "can_download": True, "can_create": True, "can_modify": True, "can_delete": True}
    return {
        "can_preview": bool(row["can_preview"]),
        "can_download": bool(row["can_download"]),
        "can_create": bool(row["can_create"]),
        "can_modify": bool(row["can_modify"]),
        "can_delete": bool(row["can_delete"]),
    }


def _current_user_can_share() -> bool:
    permissions = _current_user_permissions()
    return bool(permissions and permissions["can_create"])


def _current_storage_root() -> Path:
    """Return the single shared file-library root for every authenticated user."""
    return Path(current_app.config["FOLDER_ROOT"]).resolve()


def _stored_scope(root: Path) -> str:
    global_root = Path(current_app.config["FOLDER_ROOT"]).resolve()
    try:
        return root.resolve().relative_to(global_root).as_posix()
    except ValueError:
        raise ValueError("Storage root is outside FOLDER_ROOT")


def _root_from_stored_scope(storage_root: str | None) -> Path | None:
    # An empty string is the valid global-root scope. NULL is a legacy/incomplete
    # share and must never silently become access to the global root.
    if storage_root is None:
        return None
    global_root = Path(current_app.config["FOLDER_ROOT"]).resolve()
    candidate = (global_root / storage_root).resolve()
    try:
        candidate.relative_to(global_root)
    except ValueError:
        return None
    return candidate if candidate.is_dir() else None


def _recycle_bin_root() -> Path:
    return Path(current_app.config["RECYCLE_BIN_PATH"]).resolve()


def _recycle_item_path(token: str) -> Path | None:
    if not re.fullmatch(r"[a-f0-9]{32}", token):
        return None
    return _recycle_bin_root() / token


def _purge_expired_recycle_items() -> None:
    """Permanently remove items whose 15-day recovery window has elapsed."""
    try:
        with get_database_connection() as connection, connection.cursor() as cursor:
            ensure_management_schema(cursor)
            connection.commit()
            cursor.execute("SELECT id, item_type, trash_token FROM recycle_bin_items WHERE expires_at <= UTC_TIMESTAMP()")
            expired_items = cursor.fetchall()
            for item in expired_items:
                trash_path = _recycle_item_path(item["trash_token"])
                try:
                    if trash_path and trash_path.exists():
                        if item["item_type"] == "folder":
                            rmtree(trash_path)
                        else:
                            trash_path.unlink()
                except OSError:
                    current_app.logger.exception("Could not permanently delete recycle bin item %s", item["id"])
                    continue
                cursor.execute("DELETE FROM recycle_bin_items WHERE id=%s", (item["id"],))
            connection.commit()
    except MySQLError:
        current_app.logger.exception("Could not purge expired recycle bin items")


def _restore_scope() -> str | None:
    """Return the scope an administrator may restore, or None for all scopes."""
    permissions = _current_user_permissions()
    if not permissions:
        return ""
    if session.get("user_role") == "super_admin":
        return None
    if session.get("user_role") == "department_admin":
        return _stored_scope(_current_storage_root())
    return ""


def _restore_recycle_items(items: list[tuple[Path, Path]]) -> None:
    for original_path, recycle_path in reversed(items):
        try:
            original_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(recycle_path, original_path)
        except OSError:
            current_app.logger.exception("Could not restore recycle bin item %s", recycle_path)


def _safe_new_name(value: str) -> str | None:
    name = value.strip()
    if not name or name in {".", ".."} or len(name) > 255 or any(char in name for char in ("/", "\\", "\x00")):
        return None
    return name


def _preview_response(file_path: Path):
    """Return a safe inline preview response, never rendering active SVG content."""
    mime_type, _ = mimetypes.guess_type(file_path.name)
    if mime_type not in PREVIEW_MIME_TYPES:
        return None
    response = send_file(file_path, mimetype=mime_type, as_attachment=False, conditional=True)
    response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'; base-uri 'none'; form-action 'none'"
    return response


@files_bp.post("/upload")
def upload_file():
    if "user_email" not in session:
        return redirect(url_for("auth.login"))
    permissions = _current_user_permissions()
    if not permissions:
        return redirect(url_for("auth.login"))
    uploaded = request.files.get("file")
    directory = _safe_directory_path(_current_storage_root(), request.form.get("folder", ""))
    original_name = _safe_new_name(uploaded.filename if uploaded else "")
    if not uploaded or not directory or not original_name:
        flash("ข้อมูลไฟล์หรือโฟลเดอร์ไม่ถูกต้อง")
        return redirect(url_for("files.my_files"))
    extension = Path(original_name).suffix.lower().lstrip(".")
    if extension == "svg":
        flash("ไม่อนุญาตให้อัปโหลด SVG เพื่อป้องกัน script ที่เป็นอันตราย")
        return redirect(url_for("files.my_files"))
    with get_database_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM allowed_file_types WHERE extension=%s AND enabled=1", (extension,))
        allowed = cursor.fetchone()
    if not allowed:
        flash("ประเภทไฟล์นี้ไม่ได้รับอนุญาตให้อัปโหลด")
        return redirect(url_for("files.my_files"))
    destination = directory / original_name
    overwrite = request.form.get("overwrite") == "on"
    if destination.exists() and not permissions["can_modify"]:
        flash("คุณไม่มีสิทธิ์บันทึกทับไฟล์เดิม")
        return redirect(url_for("files.my_files"))
    if not destination.exists() and not permissions["can_create"]:
        flash("คุณไม่มีสิทธิ์สร้างไฟล์ใหม่")
        return redirect(url_for("files.my_files"))
    if destination.exists() and not overwrite:
        flash("มีไฟล์ชื่อนี้อยู่แล้ว โปรดเลือกบันทึกทับไฟล์เดิม")
        return redirect(url_for("files.my_files"))
    temporary = directory / f".{uuid4().hex}.uploading"
    try:
        uploaded.save(temporary)
        if temporary.stat().st_size > current_app.config["MAX_UPLOAD_BYTES"]:
            temporary.unlink(missing_ok=True)
            flash("ไฟล์มีขนาดเกินกำหนด")
            return redirect(url_for("files.my_files"))
        if destination.exists():
            backup = directory / f".{uuid4().hex}.replacing"
            os.replace(destination, backup)
            try:
                os.link(temporary, destination)
            except OSError:
                os.replace(backup, destination)
                raise
            temporary.unlink()
            backup.unlink()
        else:
            # link() is an atomic, no-overwrite publish operation on the same volume.
            # It prevents concurrent uploads from silently replacing an existing file.
            os.link(temporary, destination)
            temporary.unlink()
    except FileExistsError:
        temporary.unlink(missing_ok=True)
        flash("มีไฟล์ชื่อนี้อยู่แล้ว")
        return redirect(url_for("files.my_files"))
    except OSError:
        temporary.unlink(missing_ok=True)
        flash("ไม่สามารถบันทึกไฟล์ได้")
        return redirect(url_for("files.my_files"))
    record_event(session["user_email"], "upload_completed", destination.relative_to(_current_storage_root()).as_posix())
    flash("อัปโหลดไฟล์แล้ว")
    return redirect(url_for("files.my_files", folder=request.form.get("folder", "")))


@files_bp.post("/folders")
def create_folder():
    if "user_email" not in session:
        return redirect(url_for("auth.login"))
    permissions = _current_user_permissions()
    if not permissions:
        return redirect(url_for("auth.login"))
    if not permissions["can_create"]:
        flash("คุณไม่มีสิทธิ์จัดการโฟลเดอร์")
        return redirect(url_for("files.my_files"))
    parent = _safe_directory_path(_current_storage_root(), request.form.get("folder", ""))
    name = _safe_new_name(request.form.get("name", ""))
    if not parent or not name:
        flash("ชื่อโฟลเดอร์ไม่ถูกต้อง")
        return redirect(url_for("files.my_files"))
    try:
        (parent / name).mkdir()
    except FileExistsError:
        flash("มีโฟลเดอร์ชื่อนี้อยู่แล้ว")
    except OSError:
        flash("ไม่สามารถสร้างโฟลเดอร์ได้")
    else:
        record_event(session["user_email"], "folder_created", (parent / name).relative_to(_current_storage_root()).as_posix())
        flash("สร้างโฟลเดอร์แล้ว")
    return redirect(url_for("files.my_files", folder=request.form.get("folder", "")))


@files_bp.post("/folders/delete")
def delete_folder():
    permissions = _require_permission("can_delete")
    if not permissions:
        flash("คุณไม่มีสิทธิ์ลบโฟลเดอร์")
        return redirect(url_for("files.my_files"))
    root = _current_storage_root()
    relative_path = request.form.get("folder_path", "").strip()
    folder = _safe_directory_path(root, relative_path)
    if not folder or folder == root:
        flash("เลือกโฟลเดอร์ที่ต้องการลบไม่ถูกต้อง")
        return redirect(url_for("files.my_files"))
    _purge_expired_recycle_items()
    token = uuid4().hex
    recycle_path = _recycle_item_path(token)
    if not recycle_path:
        return "Internal server error", 500
    try:
        recycle_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(folder, recycle_path)
    except OSError:
        flash("ไม่สามารถย้ายโฟลเดอร์ไปยัง Recycle Bin ได้")
        return redirect(url_for("files.my_files"))
    try:
        with get_database_connection() as connection, connection.cursor() as cursor:
            ensure_management_schema(cursor)
            cursor.execute(
                "DELETE FROM file_shares WHERE storage_root=%s AND "
                "(item_name=%s OR LEFT(item_name, CHAR_LENGTH(%s) + 1)=CONCAT(%s, '/'))",
                (_stored_scope(root), relative_path, relative_path, relative_path),
            )
            cursor.execute(
                """INSERT INTO recycle_bin_items (item_type, storage_root, original_path, trash_token, deleted_by, expires_at)
                   VALUES ('folder', %s, %s, %s, %s, DATE_ADD(UTC_TIMESTAMP(), INTERVAL 15 DAY))""",
                (_stored_scope(root), relative_path, token, session["user_email"]),
            )
            connection.commit()
    except MySQLError:
        try:
            os.replace(recycle_path, folder)
        except OSError:
            current_app.logger.exception("Could not restore folder after database delete failure")
        flash("ไม่สามารถบันทึก Recycle Bin ได้ โปรดลองใหม่อีกครั้ง")
        return redirect(url_for("files.my_files"))
    record_event(session["user_email"], "folder_deleted", relative_path)
    flash("ย้ายโฟลเดอร์ไปยัง Recycle Bin แล้ว กู้คืนได้ภายใน 15 วัน")
    return redirect(url_for("files.my_files"))


@files_bp.post("/folders/rename")
def rename_folder():
    permissions = _require_permission("can_modify")
    if not permissions:
        flash("คุณไม่มีสิทธิ์เปลี่ยนชื่อโฟลเดอร์")
        return redirect(url_for("files.my_files"))
    root = _current_storage_root()
    relative_path = request.form.get("folder_path", "").strip()
    folder = _safe_directory_path(root, relative_path)
    new_name = _safe_new_name(request.form.get("new_name", ""))
    if not folder or folder == root or not new_name:
        flash("ชื่อโฟลเดอร์หรือโฟลเดอร์ต้นทางไม่ถูกต้อง")
        return redirect(url_for("files.my_files"))
    destination = folder.with_name(new_name)
    if destination.exists():
        flash("มีไฟล์หรือโฟลเดอร์ชื่อนี้อยู่แล้ว")
        return redirect(url_for("files.my_files"))
    try:
        os.replace(folder, destination)
    except OSError:
        flash("ไม่สามารถเปลี่ยนชื่อโฟลเดอร์ได้")
        return redirect(url_for("files.my_files"))
    new_relative_path = destination.relative_to(root).as_posix()
    try:
        with get_database_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE file_shares
                   SET item_name=CONCAT(%s, SUBSTRING(item_name, %s))
                   WHERE storage_root=%s AND LEFT(item_name, CHAR_LENGTH(%s) + 1)=CONCAT(%s, '/')""",
                (new_relative_path, len(relative_path) + 1, _stored_scope(root), relative_path, relative_path),
            )
            connection.commit()
    except MySQLError:
        try:
            os.replace(destination, folder)
        except OSError:
            current_app.logger.exception("Could not restore folder after share update failure")
        flash("ไม่สามารถบันทึกการเปลี่ยนชื่อโฟลเดอร์ได้ โปรดลองใหม่อีกครั้ง")
        return redirect(url_for("files.my_files"))
    record_event(session["user_email"], "folder_renamed", f"{relative_path} -> {new_relative_path}")
    flash("เปลี่ยนชื่อโฟลเดอร์แล้ว")
    return redirect(url_for("files.my_files", folder=destination.parent.relative_to(root).as_posix()))


def _folder_download_response(folder: Path):
    """Create a ZIP in memory for a selected folder without exposing host paths."""
    archive = BytesIO()
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zip_file:
        for item in folder.rglob("*"):
            if item.is_file() and not item.is_symlink():
                zip_file.write(item, (Path(folder.name) / item.relative_to(folder)).as_posix())
    archive.seek(0)
    return send_file(archive, mimetype="application/zip", as_attachment=True, download_name=f"{folder.name}.zip")


@files_bp.get("/download")
def download_file():
    """Download a selected file or a selected folder as a ZIP archive."""
    permissions = _current_user_permissions() if "user_email" in session else None
    if not permissions:
        return redirect(url_for("auth.login"))
    if not permissions["can_download"]:
        return "Not found", 404
    root = _current_storage_root()
    relative_path = request.args.get("file", "").strip()
    file_path = _safe_file_path(root, relative_path)
    if file_path:
        record_event(session["user_email"], "download_completed", file_path.relative_to(root).as_posix())
        return send_file(file_path, as_attachment=True, download_name=file_path.name)
    folder = _safe_directory_path(root, relative_path)
    if not folder or folder == root:
        return "Not found", 404
    record_event(session["user_email"], "folder_downloaded", folder.relative_to(root).as_posix())
    return _folder_download_response(folder)


def _managed_files_from_request(root: Path) -> list[Path] | None:
    paths = list(dict.fromkeys(value.strip() for value in request.form.getlist("file_paths") if value.strip()))
    if not paths and request.form.get("file_path", "").strip():
        paths = [request.form["file_path"].strip()]
    if not paths or len(paths) > MAX_MANAGED_FILES:
        return None
    resolved = [_safe_file_path(root, relative_path) for relative_path in paths]
    return resolved if all(resolved) else None


def _require_permission(permission: str) -> dict[str, bool] | None:
    if "user_email" not in session:
        return None
    permissions = _current_user_permissions()
    return permissions if permissions and permissions[permission] else None


@files_bp.post("/rename")
def rename_file():
    permissions = _require_permission("can_modify")
    if not permissions:
        flash("คุณไม่มีสิทธิ์จัดการไฟล์")
        return redirect(url_for("files.my_files"))
    root = _current_storage_root()
    source = _safe_file_path(root, request.form.get("file_path", "").strip())
    new_name = _safe_new_name(request.form.get("new_name", ""))
    if not source or not new_name:
        flash("ชื่อไฟล์หรือไฟล์ต้นทางไม่ถูกต้อง")
        return redirect(url_for("files.my_files"))
    destination = source.with_name(new_name)
    if destination.exists():
        flash("มีไฟล์ชื่อนี้อยู่แล้ว")
        return redirect(url_for("files.my_files"))
    try:
        os.link(source, destination)
        source.unlink()
    except FileExistsError:
        flash("มีไฟล์ชื่อนี้อยู่แล้ว")
        return redirect(url_for("files.my_files"))
    except OSError:
        flash("ไม่สามารถเปลี่ยนชื่อไฟล์ได้")
        return redirect(url_for("files.my_files"))
    old_path = source.relative_to(root).as_posix()
    new_path = destination.relative_to(root).as_posix()
    with get_database_connection() as connection, connection.cursor() as cursor:
        cursor.execute("UPDATE file_shares SET item_name=%s WHERE shared_by=%s AND storage_root=%s AND item_name=%s", (new_path, session["user_email"], _stored_scope(root), old_path))
        connection.commit()
    record_event(session["user_email"], "file_renamed", f"{old_path} -> {new_path}")
    flash("เปลี่ยนชื่อไฟล์แล้ว")
    return redirect(url_for("files.my_files", folder=destination.parent.relative_to(root).as_posix()))


@files_bp.post("/move")
def move_files():
    permissions = _require_permission("can_modify")
    if not permissions:
        flash("คุณไม่มีสิทธิ์จัดการไฟล์")
        return redirect(url_for("files.my_files"))
    root = _current_storage_root()
    sources = _managed_files_from_request(root)
    destination_dir = _safe_directory_path(root, request.form.get("destination_folder", ""))
    if not sources or not destination_dir:
        flash("ข้อมูลการย้ายไฟล์ไม่ถูกต้อง")
        return redirect(url_for("files.my_files"))
    destinations = [destination_dir / source.name for source in sources]
    if len({path.name.casefold() for path in destinations}) != len(destinations) or any(path.exists() for path in destinations):
        flash("โฟลเดอร์ปลายทางมีไฟล์ชื่อซ้ำอยู่แล้ว")
        return redirect(url_for("files.my_files"))
    moved: list[tuple[Path, Path]] = []
    try:
        for source, destination in zip(sources, destinations):
            os.link(source, destination)
            source.unlink()
            moved.append((source, destination))
    except OSError:
        for source, destination in reversed(moved):
            if destination.exists() and not source.exists():
                os.link(destination, source)
                destination.unlink()
        flash("ไม่สามารถย้ายไฟล์ได้")
        return redirect(url_for("files.my_files"))
    with get_database_connection() as connection, connection.cursor() as cursor:
        for source, destination in moved:
            cursor.execute("UPDATE file_shares SET item_name=%s WHERE shared_by=%s AND storage_root=%s AND item_name=%s", (destination.relative_to(root).as_posix(), session["user_email"], _stored_scope(root), source.relative_to(root).as_posix()))
        connection.commit()
    record_event(session["user_email"], "files_moved", f"{len(moved)} file(s)")
    flash("ย้ายไฟล์แล้ว")
    return redirect(url_for("files.my_files", folder=destination_dir.relative_to(root).as_posix()))


@files_bp.post("/delete")
def delete_files():
    permissions = _require_permission("can_delete")
    if not permissions:
        flash("คุณไม่มีสิทธิ์จัดการไฟล์")
        return redirect(url_for("files.my_files"))
    root = _current_storage_root()
    files = _managed_files_from_request(root)
    if not files:
        flash("ไม่พบไฟล์ที่ต้องการลบ")
        return redirect(url_for("files.my_files"))
    _purge_expired_recycle_items()
    relative_paths = [file_path.relative_to(root).as_posix() for file_path in files]
    recycle_root = _recycle_bin_root()
    recycled_files: list[tuple[Path, Path, str]] = []
    try:
        recycle_root.mkdir(parents=True, exist_ok=True)
        for file_path in files:
            token = uuid4().hex
            recycle_path = recycle_root / token
            os.replace(file_path, recycle_path)
            recycled_files.append((file_path, recycle_path, token))
    except OSError:
        _restore_recycle_items([(original_path, recycle_path) for original_path, recycle_path, _ in recycled_files])
        flash("ไม่สามารถย้ายไฟล์ไปยัง Recycle Bin ได้ครบทั้งหมด")
        return redirect(url_for("files.my_files"))
    try:
        with get_database_connection() as connection, connection.cursor() as cursor:
            ensure_management_schema(cursor)
            placeholders = ", ".join(["%s"] * len(relative_paths))
            cursor.execute(f"DELETE FROM file_shares WHERE storage_root=%s AND item_name IN ({placeholders})", [_stored_scope(root), *relative_paths])
            cursor.executemany(
                """INSERT INTO recycle_bin_items (item_type, storage_root, original_path, trash_token, deleted_by, expires_at)
                   VALUES ('file', %s, %s, %s, %s, DATE_ADD(UTC_TIMESTAMP(), INTERVAL 15 DAY))""",
                [(_stored_scope(root), original_path.relative_to(root).as_posix(), token, session["user_email"])
                 for original_path, _, token in recycled_files],
            )
            connection.commit()
    except MySQLError:
        _restore_recycle_items([(original_path, recycle_path) for original_path, recycle_path, _ in recycled_files])
        flash("ไม่สามารถบันทึก Recycle Bin ได้ โปรดลองใหม่อีกครั้ง")
        return redirect(url_for("files.my_files"))
    record_event(session["user_email"], "files_deleted", f"{len(relative_paths)} file(s)")
    flash("ย้ายไฟล์ไปยัง Recycle Bin แล้ว กู้คืนได้ภายใน 15 วัน")
    return redirect(url_for("files.my_files"))


@files_bp.get("/recycle-bin")
def recycle_bin():
    scope = _restore_scope()
    if scope == "":
        return "Forbidden", 403
    _purge_expired_recycle_items()
    with get_database_connection() as connection, connection.cursor() as cursor:
        ensure_management_schema(cursor)
        connection.commit()
        if scope is None:
            cursor.execute("SELECT id, item_type, original_path, storage_root, deleted_by, deleted_at, expires_at FROM recycle_bin_items ORDER BY deleted_at DESC")
        else:
            cursor.execute("SELECT id, item_type, original_path, storage_root, deleted_by, deleted_at, expires_at FROM recycle_bin_items WHERE storage_root=%s ORDER BY deleted_at DESC", (scope,))
        items = cursor.fetchall()
    return render_template("files/recycle_bin.html", items=items, is_super_admin=session.get("user_role") == "super_admin")


@files_bp.post("/recycle-bin/<int:item_id>/restore")
def restore_recycle_item(item_id: int):
    scope = _restore_scope()
    if scope == "":
        return "Forbidden", 403
    _purge_expired_recycle_items()
    with get_database_connection() as connection, connection.cursor() as cursor:
        ensure_management_schema(cursor)
        connection.commit()
        query = "SELECT id, item_type, storage_root, original_path, trash_token FROM recycle_bin_items WHERE id=%s"
        parameters: list[object] = [item_id]
        if scope is not None:
            query += " AND storage_root=%s"
            parameters.append(scope)
        query += " FOR UPDATE"
        cursor.execute(query, parameters)
        item = cursor.fetchone()
        if not item:
            return "Not found", 404
        root = _root_from_stored_scope(item["storage_root"])
        trash_path = _recycle_item_path(item["trash_token"])
        if not root or not trash_path or not trash_path.exists():
            return "Not found", 404
        try:
            destination = (root / item["original_path"]).resolve()
            destination.relative_to(root.resolve())
        except ValueError:
            return "Not found", 404
        if destination.exists():
            flash("กู้คืนไม่ได้ เพราะมีไฟล์หรือโฟลเดอร์ชื่อเดิมอยู่แล้ว")
            return redirect(url_for("files.recycle_bin"))
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(trash_path, destination)
            cursor.execute("DELETE FROM recycle_bin_items WHERE id=%s", (item_id,))
            connection.commit()
        except (MySQLError, OSError):
            if destination.exists() and not trash_path.exists():
                try:
                    os.replace(destination, trash_path)
                except OSError:
                    current_app.logger.exception("Could not return recycle item after restore failure")
            flash("ไม่สามารถกู้คืนรายการนี้ได้ โปรดลองใหม่อีกครั้ง")
            return redirect(url_for("files.recycle_bin"))
    record_event(session["user_email"], "recycle_item_restored", f"{item['item_type']}:{item['original_path']}")
    flash("กู้คืนรายการแล้ว")
    return redirect(url_for("files.recycle_bin"))


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
    folder_paths = list(dict.fromkeys(path.strip() for path in request.form.getlist("folder_paths") if path.strip()))
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
        or (not relative_paths and not folder_paths)
        or len(relative_paths) > MAX_SHARE_FILES
        or any(len(path) > 1024 or "\x00" in path or Path(path).is_absolute() for path in relative_paths)
        or any(len(path) > 1024 or "\x00" in path or Path(path).is_absolute() for path in folder_paths)
    ):
        flash("ข้อมูลการแชร์ไม่ถูกต้อง")
        return redirect(url_for("files.my_files"))
    root = _current_storage_root()
    storage_root = _stored_scope(root)
    for folder_path in folder_paths:
        folder = _safe_directory_path(root, folder_path)
        if not folder or folder == root:
            flash("ไม่พบโฟลเดอร์บางรายการหรือคุณไม่มีสิทธิ์แชร์")
            return redirect(url_for("files.my_files"))
        relative_paths.extend(
            item.relative_to(root).as_posix()
            for item in folder.rglob("*")
            if item.is_file() and not item.is_symlink()
        )
    relative_paths = list(dict.fromkeys(relative_paths))
    if not relative_paths or len(relative_paths) > MAX_SHARE_FILES:
        flash(f"โฟลเดอร์ที่เลือกต้องมีไฟล์ และแชร์ได้สูงสุด {MAX_SHARE_FILES} ไฟล์ต่อครั้ง")
        return redirect(url_for("files.my_files"))
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
                        f"UPDATE file_shares SET permission=%s, storage_root=%s, expires_at=DATE_ADD(UTC_TIMESTAMP(), INTERVAL {expiry_days} DAY) WHERE item_name=%s AND shared_by=%s AND recipient_email=%s",
                        (permission, storage_root, relative_path, session["user_email"], recipient),
                    )
                else:
                    cursor.execute(
                        f"INSERT INTO file_shares (item_name, storage_root, permission, expires_at, shared_by, recipient_email) VALUES (%s, %s, %s, DATE_ADD(UTC_TIMESTAMP(), INTERVAL {expiry_days} DAY), %s, %s)",
                        (relative_path, storage_root, permission, session["user_email"], recipient),
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
    permissions = _current_user_permissions()
    if not permissions:
        return redirect(url_for("auth.login"))
    if not permissions["can_preview"]:
        return "Not found", 404
    relative_path = request.args.get("file", "").strip()
    root = _current_storage_root()
    file_path = _safe_file_path(root, relative_path)
    if not file_path:
        return "Not found", 404
    response = _preview_response(file_path)
    return response if response else ("Not found", 404)


@files_bp.get("/shared-preview")
def shared_preview():
    if "user_email" not in session:
        return redirect(url_for("auth.login"))
    permissions = _current_user_permissions()
    if not permissions:
        return redirect(url_for("auth.login"))
    if not permissions["can_preview"]:
        return "Not found", 404
    owner = request.args.get("owner", "").strip().lower()
    relative_path = request.args.get("file", "").strip()
    with get_database_connection() as connection, connection.cursor() as cursor:
        ensure_management_schema(cursor)
        connection.commit()
        cursor.execute("SELECT permission, storage_root FROM file_shares WHERE recipient_email=%s AND shared_by=%s AND item_name=%s AND expires_at > UTC_TIMESTAMP() LIMIT 1", (session["user_email"], owner, relative_path))
        allowed = cursor.fetchone()
    if not allowed or allowed["permission"] not in {"view", "download"}:
        return "Not found", 404
    root = _root_from_stored_scope(allowed["storage_root"])
    if not root:
        return "Not found", 404
    file_path = _safe_file_path(root, relative_path)
    if not file_path:
        return "Not found", 404
    response = _preview_response(file_path)
    if not response:
        return "Not found", 404
    record_event(session["user_email"], "shared_file_previewed", f"{owner}:{relative_path}")
    return response


@files_bp.get("/shared-download")
def shared_download():
    if "user_email" not in session:
        return redirect(url_for("auth.login"))
    permissions = _current_user_permissions()
    if not permissions:
        return redirect(url_for("auth.login"))
    if not permissions["can_download"]:
        return "Not found", 404
    owner = request.args.get("owner", "").strip().lower()
    relative_path = request.args.get("file", "").strip()
    with get_database_connection() as connection, connection.cursor() as cursor:
        ensure_management_schema(cursor)
        connection.commit()
        cursor.execute("SELECT permission, storage_root FROM file_shares WHERE recipient_email=%s AND shared_by=%s AND item_name=%s AND expires_at > UTC_TIMESTAMP() LIMIT 1", (session["user_email"], owner, relative_path))
        allowed = cursor.fetchone()
    if not allowed or allowed["permission"] != "download":
        return "Not found", 404
    root = _root_from_stored_scope(allowed["storage_root"])
    if not root:
        return "Not found", 404
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
    permissions = _current_user_permissions()
    if not permissions:
        return redirect(url_for("auth.login"))
    _purge_expired_recycle_items()
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
    folder_root = _current_storage_root()
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
        can_restore=session.get("user_role") in {"department_admin", "super_admin"},
        permissions=permissions,
        storage=storage_summary,
        folder_tree=folder_tree,
        browser=browser,
    )
