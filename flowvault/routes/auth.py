from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from flowvault.audit import record_event
from flowvault.database import get_database_connection
from flowvault.otp import create_otp, get_gmail_settings, is_otp_enabled, save_gmail_settings, send_otp

auth_bp = Blueprint("auth", __name__)


def _current_role() -> str | None:
    if not session.get("user_id"):
        return None
    with get_database_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT role FROM users WHERE id=%s AND email=%s", (session["user_id"], session.get("user_email")))
        row = cursor.fetchone()
    return row["role"] if row else None


def _rate_limit_key(email: str) -> str:
    return sha256(f"{request.remote_addr}:{email}".encode()).hexdigest()


def _failure_count(scope_key: str) -> int:
    with get_database_connection() as connection, connection.cursor() as cursor:
        window = int(current_app.config["LOGIN_FAILURE_WINDOW_SECONDS"])
        cursor.execute(f"SELECT COUNT(*) AS count FROM auth_login_attempts WHERE scope_key=%s AND attempted_at >= UTC_TIMESTAMP() - INTERVAL {window} SECOND", (scope_key,))
        return cursor.fetchone()["count"]


def _record_failure(scope_key: str) -> None:
    with get_database_connection() as connection, connection.cursor() as cursor:
        cursor.execute("INSERT INTO auth_login_attempts (scope_key) VALUES (%s)", (scope_key,))
        cursor.execute("DELETE FROM auth_login_attempts WHERE attempted_at < UTC_TIMESTAMP() - INTERVAL 1 DAY")
        connection.commit()


def _clear_failures(scope_key: str) -> None:
    with get_database_connection() as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM auth_login_attempts WHERE scope_key=%s", (scope_key,))
        connection.commit()


@auth_bp.route("/", methods=["GET", "POST"])
def login():
    if "user_email" in session:
        return redirect(url_for("files.my_files"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        scope_key = _rate_limit_key(email)
        if _failure_count(scope_key) >= current_app.config["LOGIN_FAILURE_LIMIT"]:
            flash("ลองเข้าสู่ระบบผิดครบ 3 ครั้งแล้ว โปรดลองใหม่ใน 1 นาที")
            return render_template("auth/login.html")
        with get_database_connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT id, email, password_hash, role, department FROM users WHERE email=%s", (email,))
            user = cursor.fetchone()
        if not user or not check_password_hash(user["password_hash"], request.form.get("password", "")):
            _record_failure(scope_key)
            record_event(email, "login_failed")
            flash("อีเมลหรือรหัสผ่านไม่ถูกต้อง")
        else:
            _clear_failures(scope_key)
            record_event(user["email"], "password_verified")
            if not is_otp_enabled():
                session.clear()
                session.permanent = True
                session.update(user_id=user["id"], user_email=user["email"], user_role=user["role"], user_department=user["department"])
                record_event(user["email"], "login_completed_otp_disabled")
                return redirect(url_for("files.my_files"))
            code = create_otp()
            try:
                send_otp(user["email"], code)
            except RuntimeError:
                if user["email"] in current_app.config["ADMIN_EMAILS"]:
                    session.clear()
                    session["otp_setup_admin"] = user["email"]
                    flash("ตั้งค่า Gmail สำหรับ OTP ก่อนใช้งานครั้งแรก")
                    return redirect(url_for("auth.otp_gmail_settings"))
                flash("ไม่สามารถส่ง OTP ได้ โปรดตรวจสอบการตั้งค่า Gmail")
            except OSError:
                flash("ไม่สามารถส่ง OTP ได้ โปรดตรวจสอบการตั้งค่า Gmail")
            else:
                session.clear()
                now = datetime.now(timezone.utc)
                session.update(pending_user_id=user["id"], pending_email=user["email"], pending_role=user["role"], pending_department=user["department"], otp_hash=sha256(code.encode()).hexdigest(), otp_expires=(now + timedelta(seconds=current_app.config["OTP_TTL_SECONDS"])).timestamp(), otp_sent_at=now.timestamp(), otp_failures=0)
                return redirect(url_for("auth.verify_otp"))
    return render_template("auth/login.html")


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if "pending_user_id" not in session:
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        if session.get("otp_failures", 0) >= current_app.config["OTP_FAILURE_LIMIT"]:
            record_event(session["pending_email"], "otp_verification_locked")
            session.clear()
            flash("ลองกรอก OTP ผิดหลายครั้งเกินไป กรุณาเข้าสู่ระบบใหม่")
            return redirect(url_for("auth.login"))
        valid = datetime.now(timezone.utc).timestamp() <= session["otp_expires"] and compare_digest(sha256(request.form.get("otp", "").strip().encode()).hexdigest(), session["otp_hash"])
        if valid:
            email = session["pending_email"]
            user_id = session["pending_user_id"]
            role = session.get("pending_role", "user")
            department = session.get("pending_department")
            session.clear()
            session.permanent = True
            session["user_id"] = user_id
            session["user_email"] = email
            session["user_role"] = role
            session["user_department"] = department
            record_event(email, "login_completed")
            return redirect(url_for("files.my_files"))
        session["otp_failures"] = session.get("otp_failures", 0) + 1
        record_event(session["pending_email"], "otp_verification_failed")
        if session["otp_failures"] >= current_app.config["OTP_FAILURE_LIMIT"]:
            session.clear()
            flash("ลองกรอก OTP ผิดครบจำนวนที่กำหนด กรุณาเข้าสู่ระบบใหม่")
            return redirect(url_for("auth.login"))
        flash("OTP ไม่ถูกต้องหรือหมดอายุ")
    return render_template("auth/verify_otp.html", email=session["pending_email"])


@auth_bp.post("/resend-otp")
def resend_otp():
    if "pending_email" not in session:
        return redirect(url_for("auth.login"))
    now = datetime.now(timezone.utc).timestamp()
    remaining = current_app.config["OTP_RESEND_SECONDS"] - (now - session.get("otp_sent_at", 0))
    if remaining > 0:
        flash(f"กรุณารออีก {int(remaining) + 1} วินาทีก่อนส่ง OTP ใหม่")
    else:
        code = create_otp()
        try:
            send_otp(session["pending_email"], code)
        except (RuntimeError, OSError):
            flash("ไม่สามารถส่ง OTP ได้ โปรดตรวจสอบการตั้งค่า Gmail")
        else:
            session["otp_hash"] = sha256(code.encode()).hexdigest()
            session["otp_sent_at"] = now
            session["otp_expires"] = now + current_app.config["OTP_TTL_SECONDS"]
            record_event(session["pending_email"], "otp_resent")
            flash("ส่ง OTP ใหม่แล้ว รหัสมีอายุ 5 นาที")
    return redirect(url_for("auth.verify_otp"))


@auth_bp.route("/admin/otp-gmail-settings", methods=["GET", "POST"])
def otp_gmail_settings():
    is_bootstrap_admin = session.get("otp_setup_admin") in current_app.config["ADMIN_EMAILS"]
    if _current_role() != "super_admin" and not is_bootstrap_admin:
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        try:
            save_gmail_settings(
                request.form["sender_email"].strip(),
                request.form.get("app_password", ""),
                request.form.get("smtp_host", "smtp.gmail.com").strip(),
                int(request.form.get("smtp_port", 587)),
                request.form.get("use_tls") == "on",
                request.form.get("enabled") == "on",
            )
        except (ValueError, TypeError):
            flash("ข้อมูล SMTP ไม่ถูกต้อง กรุณาตรวจสอบอีเมล รหัสผ่าน และพอร์ต")
            return redirect(url_for("auth.otp_gmail_settings"))
        if session.get("user_email"):
            record_event(session["user_email"], "otp_gmail_settings_updated")
        flash("บันทึกการตั้งค่า OTP Gmail แล้ว")
        if is_bootstrap_admin:
            session.pop("otp_setup_admin", None)
            return redirect(url_for("auth.login"))
    settings = get_gmail_settings()
    return render_template("admin/otp_gmail_settings.html", settings=settings)


@auth_bp.get("/admin/logs")
def admin_logs():
    if _current_role() != "super_admin":
        return redirect(url_for("auth.login"))
    email = request.args.get("email", "").strip().lower()
    with get_database_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT user_email FROM audit_logs ORDER BY user_email")
        users = [row["user_email"] for row in cursor.fetchall()]
        if email:
            cursor.execute("SELECT user_email, action, detail, ip_address, created_at FROM audit_logs WHERE user_email LIKE %s ORDER BY created_at DESC LIMIT 200", (f"%{email}%",))
        else:
            cursor.execute("SELECT user_email, action, detail, ip_address, created_at FROM audit_logs ORDER BY created_at DESC LIMIT 200")
        logs = cursor.fetchall()
    return render_template("admin/logs.html", logs=logs, users=users, selected_email=email)


@auth_bp.post("/logout")
def logout():
    if session.get("user_email"):
        record_event(session["user_email"], "logout_completed")
    session.clear()
    return redirect(url_for("auth.login"))
