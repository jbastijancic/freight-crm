from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Contact(db.Model):
    __tablename__ = "contacts"

    id         = db.Column(db.String(10),  primary_key=True)
    type       = db.Column(db.String(20),  nullable=False)
    name       = db.Column(db.String(100), nullable=False)
    company    = db.Column(db.String(100), default="")
    phone      = db.Column(db.String(50),  default="")
    email      = db.Column(db.String(100), default="")
    address    = db.Column(db.String(200), default="")
    active     = db.Column(db.Boolean,     default=True)
    created_at = db.Column(db.String(10),  default="")

    notes = db.relationship(
        "Note", backref="contact", lazy=True,
        order_by="Note.date", cascade="all, delete-orphan"
    )


class Note(db.Model):
    __tablename__ = "notes"

    id         = db.Column(db.Integer,    primary_key=True, autoincrement=True)
    contact_id = db.Column(db.String(10), db.ForeignKey("contacts.id"), nullable=False)
    date       = db.Column(db.String(10))
    text       = db.Column(db.Text)


class Shipment(db.Model):
    __tablename__ = "shipments"

    id            = db.Column(db.String(10),  primary_key=True)
    status        = db.Column(db.String(20),  default="booked")
    customer_id   = db.Column(db.String(10),  default="")
    carrier_id    = db.Column(db.String(10),  default="")
    origin        = db.Column(db.String(100), default="")
    destination   = db.Column(db.String(100), default="")
    pickup_date   = db.Column(db.String(10),  default="")
    delivery_date = db.Column(db.String(10),  default="")
    rate          = db.Column(db.Float,       default=0.0)
    commodity     = db.Column(db.String(100), default="")
    weight_lbs    = db.Column(db.Integer,     default=0)
    notes         = db.Column(db.Text,        default="")
