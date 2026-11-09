from io import BytesIO
from urllib.parse import quote

import openpyxl

from app import EXPORT_HEADERS, safe_file_part


def load(resp):
    return openpyxl.load_workbook(BytesIO(resp.data)).active


def test_export_all_headers_and_rows(make_house, client):
    make_house("Villa A", colors=[{"color_name": "Sand"}, {"color_name": "Navy"}])
    make_house("Villa B", colors=[{"color_name": "Cream", "model": "easy clean"}])
    r = client.get("/export.xlsx")
    assert r.status_code == 200
    assert r.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "House_Color_Database.xlsx" in r.headers["Content-Disposition"]
    ws = load(r)
    rows = list(ws.iter_rows(values_only=True))
    assert list(rows[0]) == EXPORT_HEADERS
    assert len(rows) == 4
    assert ws.title == "House Colors"
    assert ("Villa B", "Cream", "RGB(200, 180, 150)", "#C8B496", "TOA", "EASY CLEAN", None) in rows


def test_export_headers_exact_order():
    assert EXPORT_HEADERS == ["House Name", "Color Name", "RGB", "HEX", "Manufacturing", "Model", "Image Reference"]


def test_export_house_filename(make_house, client):
    house = make_house("Villa A", colors=[{"color_name": "Sand"}])
    r = client.get(f"/houses/{house['id']}/export.xlsx")
    assert r.status_code == 200
    assert "House_Color_Villa_A.xlsx" in r.headers["Content-Disposition"]
    assert len(list(load(r).iter_rows())) == 2


def test_export_house_thai_filename(make_house, client):
    house = make_house("บ้าน สวน", colors=[{"color_name": "Sand"}])
    r = client.get(f"/houses/{house['id']}/export.xlsx")
    assert r.status_code == 200
    cd = r.headers["Content-Disposition"]
    assert "filename*=UTF-8''" + quote("House_Color_บ้าน_สวน.xlsx") in cd


def test_safe_file_part():
    assert safe_file_part('  a/b:c  d ') == "abc_d"
    assert safe_file_part("") == "House"
    assert len(safe_file_part("x" * 100)) == 80


def test_export_missing_house_404(client):
    assert client.get("/houses/999999/export.xlsx").status_code == 404
