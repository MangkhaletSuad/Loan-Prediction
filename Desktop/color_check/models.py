from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def now():
    return datetime.utcnow()


class House(db.Model):
    __tablename__ = "houses"

    id = db.Column(db.Integer, primary_key=True)
    house_name = db.Column(db.String(150), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)

    images = db.relationship(
        "HouseImage", backref="house", cascade="all, delete-orphan",
        passive_deletes=True, order_by="HouseImage.id",
    )
    colors = db.relationship(
        "Color", backref="house", cascade="all, delete-orphan",
        passive_deletes=True, order_by="Color.id",
    )

    def to_dict(self, include_children=True):
        data = {
            "id": self.id,
            "house_name": self.house_name,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
            "image_count": len(self.images),
            "color_count": len(self.colors),
        }
        if include_children:
            data["images"] = [i.to_dict() for i in self.images]
            data["colors"] = [c.to_dict() for c in self.colors]
        return data


class HouseImage(db.Model):
    __tablename__ = "house_images"

    id = db.Column(db.Integer, primary_key=True)
    house_id = db.Column(
        db.Integer, db.ForeignKey("houses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_path = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    def to_dict(self):
        return {
            "id": self.id,
            "house_id": self.house_id,
            "image_path": self.image_path,
            "url": f"/uploads/{self.image_path}",
            "original_name": self.original_name,
            "created_at": iso(self.created_at),
        }


class Color(db.Model):
    __tablename__ = "colors"

    id = db.Column(db.Integer, primary_key=True)
    house_id = db.Column(
        db.Integer, db.ForeignKey("houses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_id = db.Column(
        db.Integer, db.ForeignKey("house_images.id", ondelete="SET NULL"), nullable=True, index=True
    )
    color_name = db.Column(db.String(100), nullable=False, index=True)
    rgb = db.Column(db.String(32), nullable=False)          # "RGB(255, 255, 255)"
    hex = db.Column(db.String(7), nullable=False, index=True)  # "#FFFFFF"
    manufacturing = db.Column(db.String(100), nullable=False, index=True)
    model = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)

    image = db.relationship("HouseImage")

    def to_dict(self):
        r, g, b = parse_rgb_string(self.rgb)
        return {
            "id": self.id,
            "house_id": self.house_id,
            "house_name": self.house.house_name if self.house else None,
            "image_id": self.image_id,
            "image_path": self.image.image_path if self.image else None,
            "color_name": self.color_name,
            "rgb": self.rgb,
            "r": r, "g": g, "b": b,
            "hex": self.hex,
            "manufacturing": self.manufacturing,
            "model": self.model,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }


class Manufacturer(db.Model):
    __tablename__ = "manufacturers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "is_default": self.is_default}


def iso(dt):
    return dt.isoformat() + "Z" if dt else None


def parse_rgb_string(value):
    try:
        inner = value[value.index("(") + 1: value.index(")")]
        r, g, b = (int(p.strip()) for p in inner.split(","))
        return r, g, b
    except (ValueError, AttributeError):
        return None, None, None
