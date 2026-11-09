import os
import re
import time
import uuid

from io import BytesIO

from flask import (Flask, abort, jsonify, render_template, request, send_file,
                   send_from_directory, url_for)
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import selectinload
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from models import Color, House, HouseImage, Manufacturer, db
from models import now as utcnow

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = BASE_DIR  # app.py lives in the project root (.env, uploads/ are next to it)


def load_env_file(path):
    """Load KEY=VALUE lines from the project .env when running outside Docker.
    Variables that are already set (e.g. by docker compose) are never overridden."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(os.path.join(PROJECT_DIR, ".env"))

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "bmp"}
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP", "GIF", "BMP", "MPO"}
DEFAULT_MANUFACTURERS = ["TOA", "DELUX"]
HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


# --------------------------------------------------------------------------- #
# App factory
# --------------------------------------------------------------------------- #
def create_app(test_config=None):
    app = Flask(__name__)

    db_user = os.environ.get("DB_USER", "admin")
    db_pass = os.environ.get("DB_PASSWORD", "")
    # Docker sets DB_HOST=mysql / DB_PORT=3306. Running `python app.py` on the host
    # falls back to the MySQL port published by docker compose (MYSQL_PORT, 3321).
    db_host = os.environ.get("DB_HOST", "127.0.0.1")
    db_port = os.environ.get("DB_PORT") or os.environ.get("MYSQL_PORT", "3306")
    db_name = os.environ.get("DB_NAME", "house_colors")

    app.config.update(
        SQLALCHEMY_DATABASE_URI=(
            f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
        ),
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 280},
        # Same host folder that docker compose mounts, so both modes share images.
        UPLOAD_FOLDER=os.environ.get("UPLOAD_FOLDER", os.path.join(PROJECT_DIR, "uploads")),
        MAX_CONTENT_LENGTH=int(os.environ.get("MAX_UPLOAD_MB", "20")) * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    with app.app_context():
        init_db()

    register_routes(app)
    register_pages(app)
    register_errors(app)
    return app


def init_db(retries=30, delay=2):
    """Wait for MySQL, create tables and seed default manufacturers."""
    for attempt in range(1, retries + 1):
        try:
            db.create_all()
            break
        except OperationalError as exc:
            if attempt == retries:
                print("[init_db] giving up. Is MySQL running? Try: docker compose up -d mysql "
                      f"(connecting to {db.engine.url.host}:{db.engine.url.port})", flush=True)
                raise
            print(f"[init_db] database not ready ({attempt}/{retries}) "
                  f"at {db.engine.url.host}:{db.engine.url.port}: {exc.orig}", flush=True)
            time.sleep(delay)

    for name in DEFAULT_MANUFACTURERS:
        if not Manufacturer.query.filter(func.lower(Manufacturer.name) == name.lower()).first():
            db.session.add(Manufacturer(name=name, is_default=True))
    try:
        db.session.commit()
    except IntegrityError:  # another worker seeded concurrently
        db.session.rollback()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
class ValidationError(Exception):
    def __init__(self, errors):
        super().__init__("Validation failed")
        self.errors = errors


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError({"_": "Request body must be a JSON object."})
    return data


def clean_text(value, field, label, max_len, required=True, errors=None):
    value = (value or "").strip() if isinstance(value, str) else ("" if value is None else str(value).strip())
    value = re.sub(r"\s+", " ", value)
    if required and not value:
        errors[field] = f"{label} is required."
    elif len(value) > max_len:
        errors[field] = f"{label} must be at most {max_len} characters."
    return value


def parse_color_value(data, errors):
    """Accept r/g/b, an 'rgb' string, or a hex string. Return (r, g, b) or None."""
    rgb = None
    if all(k in data for k in ("r", "g", "b")):
        try:
            rgb = tuple(int(data[k]) for k in ("r", "g", "b"))
        except (TypeError, ValueError):
            errors["rgb"] = "R, G and B must be whole numbers."
            return None
    elif data.get("rgb"):
        nums = re.findall(r"-?\d+", str(data["rgb"]))
        if len(nums) != 3:
            errors["rgb"] = "RGB must look like RGB(255, 255, 255)."
            return None
        rgb = tuple(int(n) for n in nums)
    elif data.get("hex"):
        m = HEX_RE.match(str(data["hex"]).strip())
        if not m:
            errors["hex"] = "HEX must look like #FFFFFF."
            return None
        h = m.group(1)
        rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    else:
        errors["rgb"] = "RGB value is required."
        return None

    if any(c < 0 or c > 255 for c in rgb):
        errors["rgb"] = "Each RGB channel must be between 0 and 255."
        return None
    return rgb


def format_rgb(rgb):
    return f"RGB({rgb[0]}, {rgb[1]}, {rgb[2]})"


def format_hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def ensure_manufacturer(name):
    if not Manufacturer.query.filter(func.lower(Manufacturer.name) == name.lower()).first():
        db.session.add(Manufacturer(name=name, is_default=False))


def canonical_manufacturer(name):
    """Reuse existing casing (e.g. 'toa' -> 'TOA')."""
    existing = Manufacturer.query.filter(func.lower(Manufacturer.name) == name.lower()).first()
    return existing.name if existing else name


def find_house_by_name(name):
    return House.query.filter(func.lower(House.house_name) == name.lower()).first()


def search_conditions(q):
    """Conditions matching a free-text query across all searchable color/house fields."""
    like = f"%{q}%"
    compact = re.sub(r"[\s]", "", q)
    conds = [
        Color.color_name.ilike(like),
        Color.rgb.ilike(like),
        func.replace(Color.rgb, " ", "").ilike(f"%{compact}%"),
        Color.hex.ilike(like),
        Color.manufacturing.ilike(like),
        Color.model.ilike(like),
        House.house_name.ilike(like),
    ]
    # "255,255,255" / "255 255 255" style queries
    nums = re.findall(r"\d{1,3}", q)
    if len(nums) == 3 and re.fullmatch(r"[\sRGBrgb(),]*\d{1,3}[\s,]+\d{1,3}[\s,]+\d{1,3}[\s)]*", q):
        conds.append(Color.rgb == f"RGB({int(nums[0])}, {int(nums[1])}, {int(nums[2])})")
    return or_(*conds)


def save_upload(file_storage, house):
    original = file_storage.filename or ""
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError({"images": f"'{original}' is not an allowed image type "
                                         f"({', '.join(sorted(ALLOWED_EXTENSIONS))})."})
    # Verify real image content, not just the extension.
    try:
        img = Image.open(file_storage.stream)
        fmt = img.format
        img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValidationError({"images": f"'{original}' is not a valid image file."})
    if fmt not in ALLOWED_FORMATS:
        raise ValidationError({"images": f"'{original}' has an unsupported format ({fmt})."})

    file_storage.stream.seek(0)
    stored_ext = "jpg" if ext == "jpeg" else ext
    filename = f"{uuid.uuid4().hex}.{stored_ext}"
    file_storage.save(os.path.join(current_upload_dir(), filename))
    safe_original = re.sub(r"[^\w.\- ()]", "_", original, flags=re.UNICODE)[:255]
    return HouseImage(house=house, image_path=filename, original_name=safe_original)


def current_upload_dir():
    from flask import current_app
    return current_app.config["UPLOAD_FOLDER"]


def remove_file(filename):
    path = os.path.join(current_upload_dir(), os.path.basename(filename))
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def house_query():
    return House.query.options(
        selectinload(House.images),
        selectinload(House.colors).selectinload(Color.image),
    )


def int_arg(args, key, default):
    try:
        return int(args.get(key, default))
    except (TypeError, ValueError):
        return default


SORTABLE = {
    "color_name": Color.color_name, "rgb": Color.rgb, "hex": Color.hex,
    "manufacturing": Color.manufacturing, "model": Color.model,
    "house_name": House.house_name, "created_at": Color.created_at,
    "updated_at": Color.updated_at,
}


def query_colors(args):
    """Search, filter, sort and paginate colors. Shared by the API and the pages."""
    q = (args.get("q") or "").strip()
    mfr = (args.get("manufacturer") or "").strip()
    house_id = int_arg(args, "house_id", None)
    sort = args.get("sort") if args.get("sort") in SORTABLE else "updated_at"
    order = args.get("order") if args.get("order") in ("asc", "desc") else "desc"
    per_page = min(max(int_arg(args, "per_page", 10), 1), 100)

    query = Color.query.join(House).options(selectinload(Color.image))
    if q:
        query = query.filter(search_conditions(q))
    if mfr:
        query = query.filter(func.lower(Color.manufacturing) == mfr.lower())
    if house_id:
        query = query.filter(Color.house_id == house_id)

    col = SORTABLE[sort]
    query = query.order_by(col.asc() if order == "asc" else col.desc(), Color.id.desc())
    total = query.count()
    pages = max((total + per_page - 1) // per_page, 1)
    page = min(max(int_arg(args, "page", 1), 1), pages)
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {"items": items, "total": total, "page": page, "per_page": per_page,
            "pages": pages, "sort": sort, "order": order}


def query_houses(q="", manufacturer=""):
    """Houses (as dicts) matching a search / manufacturer filter.
    When filtered, each dict has matched_color_ids."""
    q, mfr = (q or "").strip(), (manufacturer or "").strip()
    query = house_query()
    matched_ids = None
    if q or mfr:
        cq = db.session.query(Color.id, Color.house_id).join(House)
        if q:
            cq = cq.filter(search_conditions(q))
        if mfr:
            cq = cq.filter(func.lower(Color.manufacturing) == mfr.lower())
        rows = cq.all()
        matched_ids = {r.id for r in rows}
        house_ids = {r.house_id for r in rows}
        if q and not mfr:  # houses whose name matches but have no colors yet
            house_ids |= {h.id for h in House.query.filter(House.house_name.ilike(f"%{q}%")).all()}
        query = query.filter(House.id.in_(house_ids or [-1]))

    result = []
    for h in query.order_by(House.updated_at.desc()).all():
        d = h.to_dict()
        if matched_ids is not None:
            d["matched_color_ids"] = [c["id"] for c in d["colors"] if c["id"] in matched_ids]
        result.append(d)
    return result


def manufacturers_with_usage():
    usage = dict(
        db.session.query(func.lower(Color.manufacturing), func.count(Color.id))
        .group_by(func.lower(Color.manufacturing)).all()
    )
    items = Manufacturer.query.order_by(Manufacturer.is_default.desc(), Manufacturer.name).all()
    return [{**m.to_dict(), "color_count": usage.get(m.name.lower(), 0)} for m in items]


def get_stats():
    by_mfr = (
        db.session.query(Color.manufacturing, func.count(Color.id))
        .group_by(Color.manufacturing).order_by(func.count(Color.id).desc()).all()
    )
    return {
        "houses": db.session.query(func.count(House.id)).scalar(),
        "colors": db.session.query(func.count(Color.id)).scalar(),
        "images": db.session.query(func.count(HouseImage.id)).scalar(),
        "manufacturers": db.session.query(func.count(Manufacturer.id)).scalar(),
        "colors_by_manufacturer": [{"name": n, "count": c} for n, c in by_mfr],
    }


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
def register_routes(app):

    @app.get("/api/health")
    def health():
        db.session.execute(select(1))
        return {"status": "ok"}

    # ---- Stats ------------------------------------------------------------ #
    @app.get("/api/stats")
    def stats():
        return get_stats()

    # ---- Houses ----------------------------------------------------------- #
    @app.get("/api/houses")
    def list_houses():
        return jsonify(query_houses(request.args.get("q"), request.args.get("manufacturer")))

    @app.post("/api/houses")
    def create_house():
        # Supports JSON {house_name} or multipart with house_name + images[]
        if request.content_type and request.content_type.startswith("multipart/"):
            data = request.form
        else:
            data = json_body()
        errors = {}
        name = clean_text(data.get("house_name"), "house_name", "House name", 150, errors=errors)
        if not errors and find_house_by_name(name):
            errors["house_name"] = "A house with this name already exists."
        if errors:
            raise ValidationError(errors)

        house = House(house_name=name)
        db.session.add(house)
        saved = []
        try:
            for f in request.files.getlist("images"):
                if f and f.filename:
                    img = save_upload(f, house)
                    saved.append(img.image_path)
                    db.session.add(img)
            db.session.commit()
        except Exception:
            db.session.rollback()
            for p in saved:
                remove_file(p)
            raise
        return jsonify(house.to_dict()), 201

    @app.get("/api/houses/<int:house_id>")
    def get_house(house_id):
        house = house_query().filter(House.id == house_id).first()
        if not house:
            abort(404, description="House not found.")
        return jsonify(house.to_dict())

    @app.put("/api/houses/<int:house_id>")
    def update_house(house_id):
        house = db.session.get(House, house_id) or abort(404, description="House not found.")
        data = json_body()
        errors = {}
        name = clean_text(data.get("house_name"), "house_name", "House name", 150, errors=errors)
        other = find_house_by_name(name) if not errors else None
        if other and other.id != house.id:
            errors["house_name"] = "A house with this name already exists."
        if errors:
            raise ValidationError(errors)
        house.house_name = name
        db.session.commit()
        return jsonify(house.to_dict())

    @app.delete("/api/houses/<int:house_id>")
    def delete_house(house_id):
        house = db.session.get(House, house_id) or abort(404, description="House not found.")
        files = [i.image_path for i in house.images]
        db.session.delete(house)
        db.session.commit()
        for f in files:
            remove_file(f)
        return "", 204

    # ---- Images ----------------------------------------------------------- #
    @app.post("/api/houses/<int:house_id>/images")
    def upload_images(house_id):
        house = db.session.get(House, house_id) or abort(404, description="House not found.")
        files = [f for f in request.files.getlist("images") if f and f.filename]
        if not files:
            raise ValidationError({"images": "Select at least one image to upload."})
        created, saved = [], []
        try:
            for f in files:
                img = save_upload(f, house)
                saved.append(img.image_path)
                db.session.add(img)
                created.append(img)
            house.updated_at = utcnow()
            db.session.commit()
        except Exception:
            db.session.rollback()
            for p in saved:
                remove_file(p)
            raise
        return jsonify([i.to_dict() for i in created]), 201

    @app.delete("/api/images/<int:image_id>")
    def delete_image(image_id):
        img = db.session.get(HouseImage, image_id) or abort(404, description="Image not found.")
        path = img.image_path
        Color.query.filter_by(image_id=img.id).update({"image_id": None})
        db.session.delete(img)
        db.session.commit()
        remove_file(path)
        return "", 204

    @app.get("/uploads/<path:filename>")
    def uploaded_file(filename):
        safe = os.path.basename(filename)
        if not os.path.isfile(os.path.join(current_upload_dir(), safe)):
            abort(404, description="Image file is missing.")
        resp = send_from_directory(current_upload_dir(), safe, max_age=86400)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp

    # ---- Colors ----------------------------------------------------------- #
    @app.get("/api/colors")
    def list_colors():
        result = query_colors(request.args)
        return {**result, "items": [c.to_dict() for c in result["items"]]}

    def apply_color_payload(color, data, creating):
        errors = {}
        color_name = clean_text(data.get("color_name"), "color_name", "Color name", 100, errors=errors)
        manufacturing = clean_text(data.get("manufacturing"), "manufacturing", "Manufacturing", 100, errors=errors)
        model = clean_text(data.get("model"), "model", "Model", 150, errors=errors)
        if model:
            model = model.upper()  # models are always stored in uppercase
        rgb = parse_color_value(data, errors)

        # House: existing id, or name (existing or new)
        house = None
        house_id = data.get("house_id")
        house_name = data.get("house_name")
        if house_id not in (None, ""):
            try:
                house = db.session.get(House, int(house_id))
            except (TypeError, ValueError):
                house = None
            if not house:
                errors["house_id"] = "Selected house does not exist."
        elif isinstance(house_name, str) and house_name.strip():
            name = clean_text(house_name, "house_name", "House name", 150, errors=errors)
            if "house_name" not in errors:
                house = find_house_by_name(name) or House(house_name=name)
                db.session.add(house)
        elif creating or color.house_id is None:
            errors["house_name"] = "House name is required."
        else:
            house = color.house

        image_id = data.get("image_id", color.image_id if not creating else None)
        if image_id in ("", None):
            image_id = None
        else:
            try:
                image_id = int(image_id)
            except (TypeError, ValueError):
                errors["image_id"] = "Invalid image reference."
                image_id = None
            if image_id is not None:
                img = db.session.get(HouseImage, image_id)
                if not img or house is None or img.house_id != house.id:
                    errors["image_id"] = "Image does not belong to the selected house."

        if errors:
            db.session.rollback()
            raise ValidationError(errors)

        manufacturing = canonical_manufacturer(manufacturing)
        ensure_manufacturer(manufacturing)
        color.color_name = color_name
        color.manufacturing = manufacturing
        color.model = model
        color.rgb = format_rgb(rgb)
        color.hex = format_hex(rgb)
        color.house = house
        color.image_id = image_id
        house.updated_at = utcnow()

    @app.post("/api/colors")
    def create_color():
        data = json_body()
        color = Color()
        apply_color_payload(color, data, creating=True)
        db.session.add(color)
        db.session.commit()
        return jsonify(color.to_dict()), 201

    @app.get("/api/colors/<int:color_id>")
    def get_color(color_id):
        color = db.session.get(Color, color_id) or abort(404, description="Color not found.")
        return jsonify(color.to_dict())

    @app.put("/api/colors/<int:color_id>")
    def update_color(color_id):
        color = db.session.get(Color, color_id) or abort(404, description="Color not found.")
        apply_color_payload(color, json_body(), creating=False)
        db.session.commit()
        return jsonify(color.to_dict())

    @app.delete("/api/colors/<int:color_id>")
    def delete_color(color_id):
        color = db.session.get(Color, color_id) or abort(404, description="Color not found.")
        db.session.delete(color)
        db.session.commit()
        return "", 204

    # ---- Manufacturers ---------------------------------------------------- #
    @app.get("/api/manufacturers")
    def list_manufacturers():
        return jsonify(manufacturers_with_usage())

    @app.post("/api/manufacturers")
    def create_manufacturer():
        errors = {}
        name = clean_text(json_body().get("name"), "name", "Manufacturer name", 100, errors=errors)
        if errors:
            raise ValidationError(errors)
        existing = Manufacturer.query.filter(func.lower(Manufacturer.name) == name.lower()).first()
        if existing:
            return jsonify(existing.to_dict()), 200
        m = Manufacturer(name=name)
        db.session.add(m)
        db.session.commit()
        return jsonify(m.to_dict()), 201

    @app.delete("/api/manufacturers/<int:mid>")
    def delete_manufacturer(mid):
        m = db.session.get(Manufacturer, mid) or abort(404, description="Manufacturer not found.")
        if m.is_default:
            abort(400, description="Default manufacturers cannot be deleted.")
        in_use = Color.query.filter(func.lower(Color.manufacturing) == m.name.lower()).count()
        if in_use:
            abort(409, description=f"'{m.name}' is used by {in_use} color record(s).")
        db.session.delete(m)
        db.session.commit()
        return "", 204

    # ---- Export rows as JSON (the .xlsx files are /export.xlsx pages) ------ #
    @app.get("/api/export")
    def export_rows():
        house, rows = export_data(request.args.get("house_id", type=int))
        return {"house_name": house.house_name if house else None, "rows": rows}


# --------------------------------------------------------------------------- #
# Pages (Jinja templates in templates/, CSS/JS in static/)
# --------------------------------------------------------------------------- #
# SVG path data for the icon sprite rendered once in base.html (used by Jinja and JS).
ICONS = {
    "dashboard": "M3 13h8V3H3zm0 8h8v-6H3zm10 0h8V11h-8zm0-18v6h8V3z",
    "house": "M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3z",
    "palette": "M12 3a9 9 0 0 0 0 18c1.1 0 1.8-.8 1.8-1.8 0-.5-.2-.9-.5-1.2-.3-.3-.5-.7-.5-1.2 0-1 .8-1.8 1.8-1.8H17a4 4 0 0 0 4-4c0-4.4-4-8-9-8zM6.5 12a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm3-4a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm5 0a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm3 4a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z",
    "factory": "M2 21V9l6 4V9l6 4V3h8v18zm4-4h2v-2H6zm5 0h2v-2h-2zm5 0h2v-2h-2z",
    "plus": "M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6z",
    "search": "M10 3a7 7 0 0 1 5.6 11.2l5.1 5.1-1.4 1.4-5.1-5.1A7 7 0 1 1 10 3zm0 2a5 5 0 1 0 0 10 5 5 0 0 0 0-10z",
    "download": "M11 3h2v9.2l3.3-3.3 1.4 1.4L12 16l-5.7-5.7 1.4-1.4 3.3 3.3zM4 19h16v2H4z",
    "upload": "M11 16V6.8L7.7 10.1 6.3 8.7 12 3l5.7 5.7-1.4 1.4L13 6.8V16zM4 19h16v2H4z",
    "edit": "M4 17.2V20h2.8l9.4-9.4-2.8-2.8zM19.7 7.1a1 1 0 0 0 0-1.4l-1.4-1.4a1 1 0 0 0-1.4 0l-1.3 1.3 2.8 2.8z",
    "trash": "M9 3h6l1 2h4v2H4V5h4zM6 9h12l-1 12H7zm4 2v8h1.5v-8zm2.5 0v8H14v-8z",
    "close": "M6.4 5 12 10.6 17.6 5 19 6.4 13.4 12 19 17.6 17.6 19 12 13.4 6.4 19 5 17.6 10.6 12 5 6.4z",
    "menu": "M3 6h18v2H3zm0 5h18v2H3zm0 5h18v2H3z",
    "grid": "M3 3h8v8H3zm10 0h8v8h-8zM3 13h8v8H3zm10 0h8v8h-8z",
    "list": "M3 5h18v2H3zm0 6h18v2H3zm0 6h18v2H3z",
    "image": "M4 4h16a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zm1 2v10.6l4-4 3 3 4-4 3 3V6zm4 1.5a2 2 0 1 1 0 4 2 2 0 0 1 0-4z",
    "picker": "M20.7 5.6 18.4 3.3a1 1 0 0 0-1.4 0l-3.1 3.1-1.4-1.4-1.4 1.4 1.4 1.4L4 16.3V20h3.7l8.5-8.5 1.4 1.4 1.4-1.4-1.4-1.4 3.1-3.1a1 1 0 0 0 0-1.4zM6.9 18H6v-.9l7.9-7.9.9.9z",
    "back": "M10.8 5.4 4.2 12l6.6 6.6 1.4-1.4L8 13h12v-2H8l4.2-4.2z",
    "sortUp": "M12 6l5 6H7z",
    "sortDown": "M12 18l-5-6h10z",
    "sort": "M12 4l4 5H8zm0 16-4-5h8z",
    "chevronLeft": "M14.6 6 9 12l5.6 6 1.4-1.4-4.3-4.6 4.3-4.6z",
    "chevronRight": "M9.4 6 15 12l-5.6 6L8 16.6l4.3-4.6L8 7.4z",
    "check": "M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z",
    "alert": "M12 2 1 21h22zm-1 7h2v6h-2zm0 8h2v2h-2z",
}

HOUSE_SORTS = {"house_name", "color_count", "image_count", "updated_at"}
HOUSE_PER_PAGE = (12, 24, 48)


def page_url(endpoint, args, **changes):
    """url_for(endpoint) keeping current query args, with some changed/removed (None)."""
    params = {k: v for k, v in args.items() if v not in (None, "")}
    for k, v in changes.items():
        if v in (None, ""):
            params.pop(k, None)
        else:
            params[k] = v
    return url_for(endpoint, **params)


def sort_houses(houses, sort, order):
    def key(h):
        if sort == "house_name":
            return h["house_name"].lower()
        return h[sort] if sort in ("color_count", "image_count") else (h["updated_at"] or "")
    return sorted(houses, key=key, reverse=(order == "desc"))


# ---- Excel export ---------------------------------------------------------- #
# Column order is fixed by the specification.
EXPORT_HEADERS = ["House Name", "Color Name", "RGB", "HEX", "Manufacturing", "Model", "Image Reference"]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def safe_file_part(name):
    """House name → filename part: no \\ / : * ? " < > | or control chars, spaces → _, max 80."""
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "", str(name or "").strip())
    s = re.sub(r"\s+", "_", s)[:80]
    return s or "House"


def export_data(house_id=None):
    """(house or None, rows) — one dict per color, keys in EXPORT_HEADERS order. 404 if house missing."""
    query = (
        db.session.query(Color, House)
        .join(House, Color.house_id == House.id)
        .options(selectinload(Color.image))
    )
    house = None
    if house_id:
        house = db.session.get(House, house_id) or abort(404, description="House not found.")
        query = query.filter(Color.house_id == house_id)
    rows = [
        {
            "House Name": h.house_name,
            "Color Name": c.color_name,
            "RGB": c.rgb,
            "HEX": c.hex,
            "Manufacturing": c.manufacturing,
            "Model": c.model,
            "Image Reference": (
                f"{c.image.original_name or c.image.image_path} (/uploads/{c.image.image_path})"
                if c.image else ""
            ),
        }
        for c, h in query.order_by(House.house_name, Color.id).all()
    ]
    return house, rows


def build_workbook(rows):
    """XLSX bytes: header row (bold) + one row per color, autofilter, fitted column widths."""
    wb = Workbook()
    ws = wb.active
    ws.title = "House Colors"
    ws.append(EXPORT_HEADERS)
    for row in rows:
        ws.append([row.get(h) or None for h in EXPORT_HEADERS])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(EXPORT_HEADERS))}{ws.max_row}"
    ws.freeze_panes = "A2"
    for i, header in enumerate(EXPORT_HEADERS, start=1):
        longest = max([len(header)] + [len(str(r.get(header) or "")) for r in rows])
        ws.column_dimensions[get_column_letter(i)].width = min(max(longest + 2, 10), 60)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def xlsx_response(rows, filename):
    resp = send_file(BytesIO(build_workbook(rows)), mimetype=XLSX_MIME,
                     as_attachment=True, download_name=filename, max_age=0)
    resp.headers["Cache-Control"] = "no-store"
    return resp


def sort_color_dicts(colors, sort, order):
    """Sort Color.to_dict() items by a SORTABLE key ('created_at' keeps creation order)."""
    def key(c):
        if sort == "created_at":
            return c["id"]
        v = c.get(sort) or ""
        return v.lower() if isinstance(v, str) else v
    return sorted(colors, key=key, reverse=(order == "desc"))


def register_pages(app):
    @app.context_processor
    def inject_helpers():
        return {"ICONS": ICONS, "page_url": page_url}

    @app.get("/")
    def dashboard():
        args = request.args
        q = (args.get("q") or "").strip()
        mfr = (args.get("manufacturer") or "").strip()
        view = "table" if args.get("view") == "table" else "cards"
        sort = args.get("sort") if args.get("sort") in HOUSE_SORTS else "updated_at"
        order = args.get("order") if args.get("order") in ("asc", "desc") else "desc"
        per_page = int_arg(args, "per_page", HOUSE_PER_PAGE[0])
        if per_page not in HOUSE_PER_PAGE:
            per_page = HOUSE_PER_PAGE[0]

        houses = sort_houses(query_houses(q, mfr), sort, order)
        pages = max((len(houses) + per_page - 1) // per_page, 1)
        page = min(max(int_arg(args, "page", 1), 1), pages)
        current = houses[(page - 1) * per_page: page * per_page]
        for h in current:
            h["manufacturers"] = sorted({c["manufacturing"] for c in h["colors"]})

        return render_template(
            "dashboard.html", houses=current, total=len(houses), stats=get_stats(),
            manufacturers=Manufacturer.query.order_by(Manufacturer.is_default.desc(),
                                                      Manufacturer.name).all(),
            q=q, mfr=mfr, view=view, sort=sort, order=order,
            page=page, pages=pages, per_page=per_page, per_page_options=HOUSE_PER_PAGE,
        )

    @app.get("/houses/new")
    def add_house_page():
        return render_template("add_house.html")

    @app.get("/houses/<int:house_id>")
    def house_page(house_id):
        house = house_query().filter(House.id == house_id).first()
        if not house:
            abort(404, description="This house does not exist or was deleted.")
        data = house.to_dict()
        sort = request.args.get("sort") if request.args.get("sort") in SORTABLE else "created_at"
        order = request.args.get("order") if request.args.get("order") in ("asc", "desc") else "asc"
        return render_template(
            "house_detail.html", house=data,
            colors=sort_color_dicts(data["colors"], sort, order),
            args={"house_id": house_id, "sort": sort, "order": order},
            sort=sort, order=order,
        )

    @app.get("/colors")
    def colors_page():
        result = query_colors(request.args)
        args = {
            "q": (request.args.get("q") or "").strip(),
            "manufacturer": (request.args.get("manufacturer") or "").strip(),
            "sort": result["sort"], "order": result["order"], "per_page": result["per_page"],
        }
        return render_template(
            "colors.html", result=result, colors=[c.to_dict() for c in result["items"]],
            args=args, manufacturers=manufacturers_with_usage(),
        )

    @app.get("/manufacturers")
    def manufacturers_page():
        return render_template("manufacturers.html", manufacturers=manufacturers_with_usage())

    @app.get("/export.xlsx")
    def export_all():
        _, rows = export_data()
        return xlsx_response(rows, "House_Color_Database.xlsx")

    @app.get("/houses/<int:house_id>/export.xlsx")
    def export_house(house_id):
        house, rows = export_data(house_id)
        return xlsx_response(rows, f"House_Color_{safe_file_part(house.house_name)}.xlsx")


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
def wants_json():
    return request.path.startswith(("/api/", "/uploads/"))


def register_errors(app):
    @app.errorhandler(ValidationError)
    def on_validation(err):
        return jsonify({"error": "Please fix the highlighted fields.", "fields": err.errors}), 422

    @app.errorhandler(RequestEntityTooLarge)
    def on_too_large(_):
        mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return jsonify({"error": f"Upload is too large (max {mb} MB per request)."}), 413

    @app.errorhandler(IntegrityError)
    def on_integrity(err):
        db.session.rollback()
        return jsonify({"error": "This record conflicts with existing data (duplicate value)."}), 409

    @app.errorhandler(HTTPException)
    def on_http(err):
        if wants_json():
            return jsonify({"error": err.description or err.name}), err.code
        return render_template("error.html", code=err.code, title=err.name,
                               message=err.description), err.code

    @app.errorhandler(Exception)
    def on_error(err):
        db.session.rollback()
        app.logger.exception("Unhandled error")
        if wants_json():
            return jsonify({"error": "Unexpected server error."}), 500
        return render_template("error.html", code=500, title="Server error",
                               message="Something went wrong. Please try again."), 500


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=True)
