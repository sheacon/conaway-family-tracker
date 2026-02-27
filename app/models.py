from datetime import datetime, date

from app import db

trip_person = db.Table(
    "trip_person",
    db.Column("trip_id", db.Integer, db.ForeignKey("trip.id"), primary_key=True),
    db.Column("person_id", db.Integer, db.ForeignKey("person.id"), primary_key=True),
)


class Family(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    members = db.relationship("Person", backref="family", lazy=True)


class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    default_location_label = db.Column(db.String(200), nullable=False, default="Home")
    default_location_lat = db.Column(db.Float, nullable=False, default=39.8283)
    default_location_lng = db.Column(db.Float, nullable=False, default=-98.5795)
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"), nullable=True)
    color = db.Column(db.String(7), nullable=False, default="#3388ff")


class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    destination = db.Column(db.String(200), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    people = db.relationship("Person", secondary=trip_person, backref="trips")

    @property
    def is_active(self):
        today = date.today()
        return self.start_date <= today <= self.end_date

    @property
    def is_upcoming(self):
        return self.start_date > date.today()


class Config(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200), nullable=False)
