import io
import os

from conftest import png_bytes
from models import HouseImage


def test_create_color_uppercases_model(make_house, client):
    house = make_house("Villa A")
    r = client.post("/api/colors", json={
        "color_name": "White", "r": 1, "g": 2, "b": 3, "manufacturing": "TOA",
        "model": "easy clean", "house_id": house["id"],
    })
    assert r.status_code == 201
    assert r.get_json()["model"] == "EASY CLEAN"


def test_search_by_rgb_spaced(make_house, client):
    make_house("Villa A", colors=[{"color_name": "Sand", "r": 200, "g": 180, "b": 150}])
    make_house("Villa B", colors=[{"color_name": "Navy", "r": 10, "g": 20, "b": 90}])
    data = client.get("/api/colors?q=200 180 150").get_json()
    assert data["total"] == 1
    assert data["items"][0]["color_name"] == "Sand"


def test_colors_bad_sort_falls_back(client):
    r = client.get("/api/colors?sort=DROP&order=x")
    assert r.status_code == 200
    assert r.get_json()["sort"] == "updated_at"


def test_upload_rejects_fake_png(make_house, client):
    house = make_house("Villa A")
    r = client.post(f"/api/houses/{house['id']}/images", data={
        "images": (io.BytesIO(b"not an image"), "x.png"),
    }, content_type="multipart/form-data")
    assert r.status_code == 422


def test_images_not_in_db(app, make_house):
    house = make_house("Villa A", image=True)
    with app.app_context():
        img = HouseImage.query.filter_by(house_id=house["id"]).one()
        assert img.image_path == os.path.basename(img.image_path)
        assert os.path.isfile(os.path.join(app.config["UPLOAD_FOLDER"], img.image_path))
        cols = HouseImage.__table__.columns
        assert all(c.type.python_type is not bytes for c in cols)
    assert len(png_bytes()) > 0
