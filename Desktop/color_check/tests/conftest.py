import io
import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from models import db  # noqa: E402


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "TESTING": True,
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
    })
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def png_bytes(color=(30, 90, 160), size=(4, 4)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def make_house(client):
    """Create a house (optionally with one image and colors) through the API."""

    def _make(name, colors=(), image=False):
        if image:
            resp = client.post("/api/houses", data={
                "house_name": name,
                "images": (io.BytesIO(png_bytes()), "house.png"),
            }, content_type="multipart/form-data")
        else:
            resp = client.post("/api/houses", json={"house_name": name})
        assert resp.status_code == 201, resp.get_json()
        house = resp.get_json()
        for c in colors:
            payload = {"r": 200, "g": 180, "b": 150, "manufacturing": "TOA", "model": "M1",
                       "house_id": house["id"], **c}
            r = client.post("/api/colors", json=payload)
            assert r.status_code == 201, r.get_json()
        return client.get(f"/api/houses/{house['id']}").get_json()

    return _make
