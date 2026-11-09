# Requirements: where each one is implemented

Source: the original "House Color Management System" specification (sections 1–10).
Status: ✅ = implemented. Notes say where it was verified in testing.

## 1. Main dashboard: `templates/dashboard.html`, route `dashboard()` in `app.py`
| Requirement | Status | Where |
|---|---|---|
| Houses shown as cards or a table | ✅ | Card/table toggle (`?view=cards|table`) |
| House name + uploaded image | ✅ | `safe_image` macro (`templates/macros.html`) + placeholder swap in `static/js/ui.js` |
| Each house's colors shown automatically as swatches with name + RGB | ✅ | `color_chip` macro in `templates/macros.html` |
| Total houses and total colors | ✅ | Summary cards from `get_stats()` (`app.py`) |
| Search by color name, RGB, manufacturing, model, house name | ✅ | `search_conditions()` in `app.py` (HEX also searchable) |
| Manufacturing filter (TOA, DELUX, custom brands) | ✅ | Dropdown + "colors by manufacturer" pills (`?manufacturer=`) |
| Click a house to see its full details | ✅ | Opens `/houses/:id` |

## 2. Add house / upload images: `templates/add_house.html`, `static/js/add_house.js`, `static/js/dropzone.js`, `templates/house_detail.html`
| Requirement | Status | Where |
|---|---|---|
| Add House button | ✅ | Sidebar + dashboard header |
| Upload one or many images | ✅ | Multi-file drag & drop; `POST /api/houses`, `POST /api/houses/:id/images` |
| Show the uploaded image | ✅ | Previews, then the picker on the house page |
| Click anywhere on the image to pick a color | ✅ | `static/js/picker.js` |
| RGB of that pixel detected automatically | ✅ | Canvas `getImageData` at natural resolution (verified exact: RGB(30, 90, 160)) |
| Color preview swatch | ✅ | Magnifier + readout in the picker; large swatch in the form |
| Save multiple colors for one house | ✅ | Each pick opens a new color form |

## 3. Color information form: `static/js/color_form.js`, `static/js/manufacturer_select.js`
| Requirement | Status | Where |
|---|---|---|
| Color name (required text) | ✅ | Checked in the browser and on the server |
| RGB auto-filled from the click, editable by hand | ✅ | Sliders + number inputs |
| Interactive RGB color picker | ✅ | Native color input + sliders |
| Shown as `RGB(255, 255, 255)` + HEX | ✅ | Preview panel; HEX also editable |
| Manufacturing: searchable dropdown with TOA and DELUX | ✅ | `mountManufacturerSelect` combobox; defaults seeded in `init_db()` |
| Custom manufacturers can be entered and are saved for next time | ✅ | `ensure_manufacturer()` in `app.py`; `templates/manufacturers.html` |
| Model (required free text) | ✅ | Forced to UPPERCASE while typing and on the server |
| House name: pick an existing house or create a new one | ✅ | Select + "Create new house" option; backend accepts `house_id` or `house_name` |

## 4. House details page: `templates/house_detail.html`, `static/js/house_detail.js`
| Requirement | Status | Where |
|---|---|---|
| House name, images, all colors, swatches, names, RGB/HEX, manufacturing, model | ✅ | Header, image strip, swatch tiles, `templates/_color_table.html` |
| Buttons: add color, edit, delete, upload more images, export this house | ✅ | Header actions + table row actions (plus rename house, delete image, delete house) |

## 5. Excel export: `export_data()` / `build_workbook()` in `app.py`, `GET /export.xlsx`, `GET /houses/<id>/export.xlsx`
| Requirement | Status | Where |
|---|---|---|
| XLSX format via an XLSX library | ✅ | openpyxl 3.1.5 (server-side) |
| Export all | ✅ | Dashboard / All Colors → `House_Color_Database.xlsx` |
| Export a single house | ✅ | House page → `House_Color_<Name>.xlsx` (verified `House_Color_Villa_A.xlsx`) |
| Exact column order: House Name, Color Name, RGB, HEX, Manufacturing, Model, Image Reference | ✅ | `EXPORT_HEADERS` |
| One row per color, all records kept, clear headers | ✅ | Plus bold header, autofilter and auto column widths |

## 6. Database design: `models.py`
| Requirement | Status | Where |
|---|---|---|
| `houses` (id, house_name, created_at, updated_at) | ✅ | `House` |
| `house_images` (id, house_id, image_path, created_at) | ✅ | `HouseImage` (+ original_name) |
| `colors` (id, house_id, image_id, color_name, rgb, hex, manufacturing, model, created_at, updated_at) | ✅ | `Color` |
| One house → many images and many colors | ✅ | Foreign keys (CASCADE / SET NULL) |
| (extra) `manufacturers` table for saved custom brands | ✅ | `Manufacturer` |

## 7. UI / UX: `static/css/styles.css`
| Requirement | Status | Where |
|---|---|---|
| Minimal, light background, dark text, blue accent | ✅ | CSS variables in `:root` |
| Responsive (desktop / tablet / mobile) | ✅ | Breakpoints at 1100 / 900 / 600px; no sideways scroll at 390px |
| Sidebar navigation | ✅ | `templates/base.html`; becomes a hamburger menu on mobile |
| Dashboard summary cards | ✅ | |
| Tables with sorting and pagination | ✅ | `sort_header`, `pagination` macros; server-side via GET parameters |
| Clean forms with validation | ✅ | Inline field errors; server returns 422 with per-field messages |
| No excessive animation or gradients | ✅ | Respects reduced-motion settings |

## 8. Technical requirements
| Requirement | Status | Where |
|---|---|---|
| Frontend | ✅ | Flask + Jinja templates (`templates/`, `static/`); replaced the React frontend at the user's request |
| Flask backend | ✅ | `app.py` (`python app.py`, runs on the host) |
| MySQL 8.4 | ✅ | `docker-compose.yml` |
| DB connection via environment variables | ✅ | `.env` → `DB_*` |
| Docker + Docker Compose | ✅ | `docker-compose.yml`: MySQL + phpMyAdmin only (the app does not run in Docker, at the user's request) |
| phpMyAdmin | ✅ | Port 8080 |
| Images stored as files, paths in MySQL, never image data in the DB | ✅ | Files in host folder `uploads/` (bind mount), only the path in `house_images.image_path` |
| CRUD | ✅ | Houses, images, colors, manufacturers |
| Input validation, missing-image handling, secure upload checks | ✅ | `save_upload()` (file extension + real image check), UUID filenames, path traversal blocked |

## 9. Important functional requirements
| Requirement | Status |
|---|---|
| Multiple colors per house | ✅ |
| Multiple images per house | ✅ |
| Click reads the exact pixel RGB | ✅ |
| RGB editable by hand | ✅ |
| Dashboard summarizes each house's colors automatically | ✅ |
| Search works across all specified fields | ✅ |
| Export all houses and a single house | ✅ |
| Data survives a Docker restart | ✅ (MySQL volume `mysql_data`, images in `uploads/`) |

## 10. Deliverables
| Requirement | Where |
|---|---|
| Complete source code | `app.py`, `models.py`, `templates/`, `static/` |
| Database configuration | `models.py`, `.env.example` |
| Docker Compose configuration | `docker-compose.yml` |
| Setup instructions | `README.md` |
| Tests | `tests/` (pytest) |
