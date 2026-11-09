# Flask Templates Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the React/Vite/nginx frontend with Flask + Jinja templates served by `backend/app.py`. Only MySQL and phpMyAdmin run in Docker. The application runs on the host with `python app.py`.

**Architecture:**
- **Pages:** Flask renders them server-side with Jinja2 (`backend/templates/`). Search, filter, sort and pagination are plain GET query parameters, so every list page works without JS.
- **Interactive parts:** the pixel picker, the color form modal, the manufacturer combobox, uploads and delete/rename actions are small vanilla-JS ES modules in `backend/static/js/`. They call the existing (already tested) `/api/*` JSON endpoints and reload the page or update the DOM.
- **Excel:** export moves to the server with openpyxl, because there is no longer a JS build step to bundle SheetJS.

**Tech Stack:** Python 3.12, Flask 3.0.3, Jinja2, Flask-SQLAlchemy 3.1.1, PyMySQL, Pillow, openpyxl 3.1.5, pytest 8.3.3. Vanilla JS (ES modules, no build). MySQL 8.4 and phpMyAdmin 5.2 in Docker.

**Spec:**
- The user's request of 2026-11-09:
  1. Move the frontend into Flask, inside `app.py`.
  2. Use templates for the frontend.
  3. Delete the frontend Dockerfile; the program must not run in Docker.
  4. Docker contains only phpMyAdmin and MySQL.
- The original feature spec, as tracked in `REQUIREMENTS.md`. Every feature listed there must still work after the port.

## Global Constraints

- **No app containers:** `docker-compose.yml` has exactly two services, `mysql` (mysql:8.4) and `phpmyadmin` (phpmyadmin:5.2). There is no `backend` or `frontend` service and no Dockerfile anywhere in the repo.
- **Run command:** the app runs with `cd backend && python app.py` on port 5000 (host `0.0.0.0`), using `venv` at the project root.
- **Frontend location:** all page routes are registered in `backend/app.py`. Templates live in `backend/templates/`, CSS and JS in `backend/static/`. There is no Node, npm or build step, and the `frontend/` directory is deleted.
- **Images:** files stay in `<project>/uploads/` on the host. MySQL stores only the filename in `house_images.image_path`, never image bytes.
- **Export columns (exact order):** `House Name, Color Name, RGB, HEX, Manufacturing, Model, Image Reference`.
- **Export filenames:** `House_Color_Database.xlsx` (all houses) and `House_Color_<SafeName>.xlsx` (one house). SafeName is the name trimmed, with `\ / : * ? " < > |` and control characters removed, whitespace runs replaced by `_`, cut to 80 chars, and `House` if empty. Example: `Villa A` gives `House_Color_Villa_A.xlsx`.
- **Model:** stored and displayed in UPPERCASE. The input uppercases as the user types and keeps the caret in place.
- **RGB format:** `RGB(r, g, b)`. HEX format: `#RRGGBB`.
- **Look:** keep the existing look. Port `frontend/src/styles.css` as-is to `backend/static/css/styles.css`, and keep its class names (`sidebar`, `card`, `table-wrap`, `chip`, `swatch`, `modal`, `toast`, …) in the templates.
- **Escaping:** user text (house/color/model/manufacturer names) is never inserted with `|safe` in Jinja, or with `innerHTML` in JS. Use autoescape and `textContent` / `createElement`.
- **No native dialogs:** no `window.alert`, `window.confirm` or `window.prompt`. Use the in-page confirm dialog and toasts from `static/js/ui.js`.
- **JSON API:** the existing `/api/*` endpoints keep their current request and response shapes.

## Review Focus

1. **Thai or other non-ASCII house names.**
   - `House_Color_<name>.xlsx` must download with the Thai name intact, via an RFC 5987 `filename*` header with an ASCII fallback, and must not raise.
   - **Test:** `test_export_house_thai_filename` in Task 5.
2. **HTML or script in names**, e.g. house name `<script>alert(1)</script>`.
   - The text must render escaped on every page, and in JS-built rows and toasts.
   - **Test:** `test_dashboard_escapes_house_name` in Task 2. Browser check in Task 4.
3. **Garbage query params**, e.g. `?page=abc`, `?page=-5`, `?page=9999`, `?sort=DROP`, `?order=sideways`, `?per_page=100000`.
   - Pages must render 200, with page clamped to `[1, pages]`, unknown sort falling back to `updated_at desc`, and per_page capped at 100.
   - **Test:** `test_colors_page_bad_params` in Task 3.
4. **Pixel picking accuracy** with images shown scaled down.
   - Clicking must still give the exact source pixel, so the canvas must not be tainted. Images are served same-origin from `/uploads/`.
   - **Check:** browser verification step in Task 4, using a generated image of solid RGB(30, 90, 160).
5. **Missing house or missing image file.**
   - `/houses/999999` must return a styled 404 page, not a JSON error or stack trace.
   - An image row whose file was deleted from disk must show the "No image" placeholder, not a broken icon.
   - **Test:** `test_house_page_404` in Task 4. Placeholder checked in the browser step.

---

### Task 0: Repository setup

The current git repo root is `C:/Users/Kong` (the whole home folder), so a project-local repo is created first.

**Files:**
- Modify: `.gitignore` (add `venv/`, `.pytest_cache/`, `.superpowers/`)

- [ ] **Step 1:** From `C:\Users\Kong\Desktop\color_check`, run `git init -b main`.
- [ ] **Step 2:** Add the three ignore lines.
- [ ] **Step 3:** Run `git status --short` and confirm that `.env`, `venv/`, `node_modules/`, `uploads/*` and `frontend/dist/` are not listed.
- [ ] **Step 4:** Commit the current working state with message `chore: snapshot before Flask-templates port`.
- [ ] **Step 5:** Run `git checkout -b flask-templates`.

### Task 1: Testable app factory and test harness

**Files:**
- Modify: `backend/app.py`
- Modify: `backend/requirements.txt` (remove `gunicorn==23.0.0`; add `openpyxl==3.1.5`, `pytest==8.3.3`)
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_api.py`

**Interfaces:**
- **Produces `create_app(test_config: dict | None = None) -> Flask`:**
  - When `test_config` is given, apply it after the defaults and before `db.init_app`.
  - `{"SQLALCHEMY_DATABASE_URI": "sqlite://", "TESTING": True, "UPLOAD_FOLDER": tmp}` must work.
  - With sqlite, skip `SQLALCHEMY_ENGINE_OPTIONS` pool settings.
  - Delete the module-level `app = create_app()`. `if __name__ == "__main__":` creates the app and runs `app.run(host="0.0.0.0", port=5000, debug=True)`.
- **Produces `query_colors(args: Mapping) -> dict`:**
  - Returns `{"items": list[Color], "total": int, "page": int, "per_page": int, "pages": int, "sort": str, "order": str}`.
  - This is the body of today's `list_colors`, moved to module level.
  - Unknown `sort` becomes `"updated_at"`; `order` not in `{"asc", "desc"}` becomes `"desc"`.
  - Page is clamped to `[1, pages]`; per_page to `[1, 100]`, default 10.
  - Non-integer page or per_page falls back to the default.
- **Produces `query_houses(q: str, manufacturer: str) -> list[dict]`:** today's `list_houses` logic moved to module level. Returns the same dicts the API returns.
- `/api/colors` and `/api/houses` become thin wrappers that serialise those results. JSON output is byte-for-byte the same shape as today.
- Delete the SPA catch-all `frontend()` route and the `FRONTEND_DIST` logic.
- **conftest fixtures:**
  - `app`: uses `sqlite://` and `tmp_path` for uploads; runs `init_db` (TOA/DELUX are seeded).
  - `client`.
  - `make_house(name, colors=[...])`: a helper that creates rows through the API and returns the house dict.

- [ ] **Step 1: Write the failing tests in `test_api.py`**
  - `test_create_color_uppercases_model`: POST a color with `model="easy clean"`; response `model == "EASY CLEAN"`.
  - `test_search_by_rgb_spaced`: color 200,180,150; `GET /api/colors?q=200 180 150` gives `total == 1`.
  - `test_colors_bad_sort_falls_back`: `GET /api/colors?sort=DROP&order=x` gives 200 and `sort == "updated_at"`.
  - `test_upload_rejects_fake_png`: multipart `images` with bytes `b"not an image"` named `x.png` gives 422.
  - `test_images_not_in_db`: upload a real 4×4 PNG made with Pillow; the `house_images.image_path` value is a bare filename that exists in `UPLOAD_FOLDER`, and no column holds bytes.
- [ ] **Step 2:** Run `cd backend && ..\venv\Scripts\python -m pytest tests -q`. Expected: errors, because `create_app` takes no arguments.
- [ ] **Step 3:** Implement the factory change, `query_colors` and `query_houses`, and remove the catch-all route.
- [ ] **Step 4:** Run the same command. Expected: all pass.
- [ ] **Step 5:** Commit with message `refactor: testable app factory, extract query helpers, drop SPA route`.

### Task 2: Base layout, static assets, Dashboard page

**Files:**
- Create: `backend/static/css/styles.css` (copy of `frontend/src/styles.css`)
- Create: `backend/static/js/ui.js`
- Create: `backend/static/js/api.js`
- Create: `backend/static/js/color.js`
- Create: `backend/templates/base.html`
- Create: `backend/templates/macros.html`
- Create: `backend/templates/dashboard.html`
- Create: `backend/templates/404.html`
- Modify: `backend/app.py` (page routes)
- Create: `backend/tests/test_pages.py`

**Interfaces:**
- **Consumes:** `query_houses`; the `/api/stats` logic, moved to module-level `get_stats() -> dict`.
- **Produces `base.html`:**
  - Sidebar nav: Dashboard `/`, All Colors `/colors`, Add House `/houses/new`, Manufacturers `/manufacturers`. The active item comes from `request.endpoint`.
  - A mobile hamburger, `{% block content %}` and `{% block scripts %}`.
  - A `#toast-root` element, and a `<dialog id="confirm-dialog">`.
- **Produces `macros.html`:** `swatch(hex)`, `color_chip(color)` (swatch + name + `RGB(…)`), `pagination(page, pages, endpoint, args)`, `sort_header(label, field, sort, order, endpoint, args)`, `empty_state(title, text)`.
- **Produces `static/js/ui.js`:**
  - `toast(message: string, kind = "info")`
  - `confirmDialog({title, message, confirmText = "Delete"}) -> Promise<boolean>`
  - `openModal(contentEl) -> {close()}`
  - `el(tag, attrs, ...children)`, a DOM builder that only sets text via `textContent`.
- **Produces `static/js/api.js`:**
  - `api.get/post/put/del(path, body?)` and `api.upload(path, formData)`.
  - These throw `ApiError {status, message, fields}`.
  - Port this from `frontend/src/lib/api.js`.
- **Produces `static/js/color.js`:** port of `frontend/src/lib/color.js` (`clampChannel`, `toHex`, `fromHex`, `formatRgb`, `isLight`).
- **Produces page route `GET /` (endpoint `dashboard`):**
  - Query params: `q`, `manufacturer`, `view` (`cards` | `table`, default `cards`).
  - Renders stats cards (total houses, total colors, colors per manufacturer), the search form, the manufacturer `<select>` and the house cards or table, each with `color_chip`s.
  - When filtered, show matched colors only, the same as `matched_color_ids` today.
  - "Export all" is a link to `/export.xlsx`.
- **404 handling:** `errorhandler(404)` renders `404.html` for non-`/api/` paths and keeps JSON for `/api/` paths.

- [ ] **Step 1: Write the failing tests in `test_pages.py`**
  - `test_dashboard_lists_houses`: create `Villa A` with color `Warm White`; `GET /` gives 200, the HTML contains `Villa A`, `Warm White` and `RGB(`.
  - `test_dashboard_search_filters`: houses `Villa A` (TOA) and `Villa B` (DELUX); `GET /?q=Villa B` contains `Villa B` and not `Villa A`.
  - `test_dashboard_manufacturer_filter`: `GET /?manufacturer=DELUX` shows only the DELUX house.
  - `test_dashboard_escapes_house_name`: house `<script>alert(1)</script>`; the HTML contains `&lt;script&gt;` and not `<script>alert(1)`.
  - `test_unknown_page_404_html`: `GET /nope` gives 404 with `text/html`.
  - `test_unknown_api_404_json`: `GET /api/nope` gives 404 with `application/json`.
- [ ] **Step 2:** Run `pytest tests/test_pages.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement the templates, static files and the route.
- [ ] **Step 4:** Run `pytest tests -q`. Expected: all pass.
- [ ] **Step 5: Browser check.**
  - Run `python app.py` and open `http://localhost:5000/`.
  - The sidebar, stats and cards render; card/table toggle, search and filter work.
  - At 390px width the hamburger menu shows and there is no horizontal scroll.
- [ ] **Step 6:** Commit with message `feat: Jinja base layout and dashboard page`.

### Task 3: All Colors page and Manufacturers page

**Files:**
- Create: `backend/templates/colors.html`
- Create: `backend/templates/manufacturers.html`
- Create: `backend/templates/_color_table.html` (shared with Task 4)
- Create: `backend/static/js/manufacturers.js`
- Create: `backend/static/js/color_actions.js`
- Modify: `backend/app.py`
- Modify: `backend/tests/test_pages.py`

**Interfaces:**
- **Consumes:** `query_colors`, macros, `ui.js`, `api.js`.
- **Produces `_color_table.html`:**
  - Include with context `colors`, `sort`, `order`, `show_house: bool`, `endpoint`, `args`.
  - Sortable columns: swatch, color name, RGB, HEX, manufacturing, model, (house), updated.
  - Each row has `data-color-id` plus Edit and Delete buttons (`.js-edit-color`, `.js-delete-color`).
- **Produces `static/js/color_actions.js`:**
  - `bindColorActions(root, {onEdit(colorId)})`.
  - Delete: confirm, then `DELETE /api/colors/:id`, then a toast and `location.reload()`.
  - Edit calls `onEdit`.
- **Produces `GET /colors` (endpoint `colors_page`):** query params `q`, `manufacturer`, `sort`, `order`, `page`, `per_page`. Server-side pagination; "Export all" link.
  - On this page, Edit opens the color form from Task 4.
  - Until Task 4 lands, Edit navigates to `/houses/<house_id>#color-<id>`.
- **Produces `GET /manufacturers` (endpoint `manufacturers_page`):**
  - A table of name, default flag and usage count.
  - An add form (POST via `api.post('/api/manufacturers')`).
  - Delete is enabled only for custom brands with 0 uses. On a 409 the server message is shown in a toast.

- [ ] **Step 1: Write the failing tests**
  - `test_colors_page_paginates`: 12 colors; `GET /colors?per_page=10&page=2` shows 2 rows (count `data-color-id`).
  - `test_colors_page_sort_by_name`: colors `B`, `A`; `GET /colors?sort=color_name&order=asc` has `A` before `B`.
  - `test_colors_page_bad_params`: each of `?page=abc`, `?page=-5`, `?page=9999`, `?sort=DROP&order=sideways`, `?per_page=100000` gives 200.
  - `test_manufacturers_page_lists_defaults`: `GET /manufacturers` contains `TOA` and `DELUX`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement the pages and JS.
- [ ] **Step 4:** Run `pytest tests -q`. Expected: all pass.
- [ ] **Step 5: Browser check.** Sort headers toggle asc/desc, pagination links keep `q` and the filter, adding/deleting a custom manufacturer works, and no native dialog appears.
- [ ] **Step 6:** Commit with message `feat: colors and manufacturers pages`.

### Task 4: House detail page, Add House page, picker and color form

**Files:**
- Create: `backend/templates/house_detail.html`
- Create: `backend/templates/add_house.html`
- Create: `backend/static/js/picker.js`
- Create: `backend/static/js/color_form.js`
- Create: `backend/static/js/manufacturer_select.js`
- Create: `backend/static/js/dropzone.js`
- Create: `backend/static/js/house_detail.js`
- Create: `backend/static/js/add_house.js`
- Modify: `backend/static/js/color_actions.js` (wire Edit on `/colors` to `openColorForm`)
- Modify: `backend/app.py`
- Modify: `backend/tests/test_pages.py`

**Interfaces:**
- **Consumes:** `ui.js`, `api.js`, `color.js`, `_color_table.html`, `bindColorActions`.
- **Produces `GET /houses/new` (endpoint `add_house_page`):**
  - A name input and a dropzone (multiple files; png, jpg, jpeg, webp, gif, bmp; max 20 MB each).
  - Submit sends multipart `POST /api/houses` (fields `house_name`, `images`), then redirects to `/houses/<id>`.
  - On 422 it shows the field errors inline.
- **Produces `GET /houses/<int:house_id>` (endpoint `house_page`):**
  - Missing house: 404 HTML.
  - Shows header (name + Rename, Upload images, Add color, Export Excel → `/houses/<id>/export.xlsx`, Delete house), the image strip with thumbnails and a delete button per image, the picker canvas, swatch tiles and `_color_table.html` (`show_house=False`).
  - The page embeds `{{ house_json|tojson }}` in `<script type="application/json" id="house-data">`.
- **Produces `static/js/picker.js`:**
  - `mountPicker(container, imageUrl, onPick({r, g, b, imageId}))`.
  - Draw at natural size; map the click from display to source pixels; `getImageData(x, y, 1, 1)`.
  - Loupe magnifier on hover. Port this from `frontend/src/components/ImagePicker.jsx`.
- **Produces `static/js/color_form.js`:**
  - `openColorForm({color?, houseId?, imageId?, rgb?, houses, manufacturers}) -> Promise<savedColor | null>`.
  - The modal is ported from `ColorForm.jsx`:
    - color name;
    - RGB sliders, number inputs, native color input and HEX field;
    - the `RGB(r, g, b)` and HEX preview;
    - manufacturer combobox;
    - model, forced uppercase and caret-preserving;
    - house select with a "Create new house" option;
    - image reference select.
  - It validates in the client and maps 422 `fields` to inline errors.
- **Produces `static/js/manufacturer_select.js`:** `mountManufacturerSelect(input, manufacturers)`, a searchable list with an "Add “X” as new manufacturer" option.
- **Produces `static/js/dropzone.js`:** `mountDropzone(el, {onFiles(File[])})`, which filters by type and size and toasts about rejected files.
- **Missing image files:** an `<img>` whose file is gone shows the "No image" placeholder through an `onerror` handler set in JS, not inline HTML.

- [ ] **Step 1: Write the failing tests**
  - `test_house_page_renders`: house with 1 image and 1 color; `GET /houses/<id>` gives 200 and contains the house name, `/uploads/<image_path>` and the color name.
  - `test_house_page_404`: `GET /houses/999999` gives 404 `text/html`.
  - `test_house_page_embeds_json_escaped`: house name `</script><b>x`; the `house-data` script block contains no literal `</script><b>` (Jinja `tojson` escapes `<`).
  - `test_add_house_page_renders`: `GET /houses/new` gives 200 and contains `name="house_name"`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement the templates and JS modules.
- [ ] **Step 4:** Run `pytest tests -q`. Expected: all pass.
- [ ] **Step 5: Browser check (Chrome)**
  - **Pixel check:** generate a 1600×1000 PNG of solid RGB(30, 90, 160) and create a house with it. Click the scaled-down picker: the form opens with `RGB(30, 90, 160)` / `#1E5AA0`.
  - **Model check:** type `easy clean` into Model; it shows `EASY CLEAN`, and the caret stays in place when you edit mid-word.
  - **Save and edit:** save the color and edit it; delete it with the in-page confirm.
  - **Uploads and house actions:** upload a second image, delete it, rename the house, delete the house.
  - **Escaping:** a house named `<b>x</b>` shows the literal text everywhere.
  - **Missing file:** delete one image file from `uploads/` by hand; the page shows the placeholder.
- [ ] **Step 6:** Commit with message `feat: house detail and add house pages with picker and color form`.

### Task 5: Server-side Excel export

**Files:**
- Modify: `backend/app.py`
- Create: `backend/tests/test_export.py`

**Interfaces:**
- **Produces `EXPORT_HEADERS: list[str]`:** the exact order from Global Constraints.
- **Produces `safe_file_part(name: str) -> str`:** implements the rule in Global Constraints.
- **Produces `build_workbook(rows: list[dict]) -> bytes`:**
  - openpyxl, one sheet titled `House Colors`.
  - The header row is bold, the sheet has an autofilter over the used range, and column widths are `min(max(longest + 2, 10), 60)`.
- **Produces `GET /export.xlsx`:** all houses.
- **Produces `GET /houses/<int:house_id>/export.xlsx`:** one house, 404 if missing.
- Both use the row data of today's `/api/export`.
- Both send mimetype `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` as an attachment.
- Use `send_file(BytesIO, download_name=...)` so Flask writes both `filename` (ASCII fallback) and `filename*` (UTF-8).

- [ ] **Step 1: Write the failing tests**
  - `test_export_all_headers_and_rows`: 2 houses with 3 colors; load the response with `openpyxl.load_workbook(BytesIO(resp.data))`. Row 1 equals `EXPORT_HEADERS`, there are 4 rows in total, and the content-disposition contains `House_Color_Database.xlsx`.
  - `test_export_house_filename`: house `Villa A`; the content-disposition contains `House_Color_Villa_A.xlsx`.
  - `test_export_house_thai_filename`: house `บ้าน สวน`; 200, and the content-disposition contains `filename*=UTF-8''House_Color_` followed by the percent-encoded `บ้าน_สวน.xlsx`.
  - `test_safe_file_part`: `'  a/b:c  d '` gives `'abc_d'`; `''` gives `'House'`; an input of 100 `x` characters gives length 80.
  - `test_export_missing_house_404`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement the export.
- [ ] **Step 4:** Run `pytest tests -q`. Expected: all pass.
- [ ] **Step 5:** Commit with message `feat: server-side xlsx export with openpyxl`.

### Task 6: Docker reduced to MySQL + phpMyAdmin; remove the React frontend; docs

**Files:**
- Modify: `docker-compose.yml` (keep only the `mysql` and `phpmyadmin` services and the `mysql_data` volume)
- Delete: `frontend/` (whole directory: Dockerfile, nginx.conf, src, dist, node_modules, package files)
- Delete: `backend/Dockerfile`
- Delete: `backend/.dockerignore`
- Modify: `.env.example` and `.env` (remove `APP_PORT`)
- Modify: `.gitignore` (remove `node_modules/` and `dist/`)
- Modify: `README.md`
- Modify: `REQUIREMENTS.md`

- [ ] **Step 1:** Edit `docker-compose.yml`.
- [ ] **Step 2:** Run `docker compose up -d --remove-orphans`. This stops and removes the `housecolor-backend` and `housecolor-frontend` containers; the database volume and `uploads/` are untouched.
- [ ] **Step 3:** Run `docker compose ps --format "{{.Name}}"`. Expected: exactly `housecolor-mysql` and `housecolor-phpmyadmin`.
- [ ] **Step 4:** Delete the files and directory listed above.
- [ ] **Step 5:** Run `git ls-files | grep -i dockerfile`. Expected: no output.
- [ ] **Step 6:** Rewrite the README.
  - **Quick start:** `docker compose up -d`, then `venv` activation, `pip install -r backend\requirements.txt`, `cd backend`, `python app.py`, then open `http://localhost:5000`.
  - Running the tests: `python -m pytest tests -q`.
  - Template and static layout.
  - The export is now server-side.
  - Keep the storage, schema, API and security sections.
- [ ] **Step 7:** Update the `REQUIREMENTS.md` "where" columns to the new template and JS paths.
- [ ] **Step 8:** Run `pytest tests -q`. Expected: all pass.
- [ ] **Step 9:** Run `python app.py` and check that `GET http://localhost:5000/` gives 200 and the existing data shows.
- [ ] **Step 10:** Commit with message `chore: run app on host only; docker = mysql + phpmyadmin; remove React frontend`.
