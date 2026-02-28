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
    email = db.Column(db.String(254), nullable=True)
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"), nullable=True)
    color = db.Column(db.String(7), nullable=False, default="#3388ff")


class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    destination = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    people = db.relationship("Person", secondary=trip_person, backref="trips")

    @property
    def display_name(self) -> str:
        return self.title if self.title else self.destination

    @property
    def is_active(self):
        today = date.today()
        return self.start_date <= today <= self.end_date

    @property
    def is_upcoming(self):
        return self.start_date > date.today()

    @property
    def is_multi_stop(self) -> bool:
        return len(self.stops) > 1

    @property
    def destinations_summary(self) -> str:
        """E.g. 'Nashville → Memphis → Nashville' with consecutive dedup."""
        if not self.stops:
            return self.destination
        names = []
        for stop in self.stops:
            if not names or names[-1] != stop.destination:
                names.append(stop.destination)
        return " → ".join(names)

    def current_stop(self, for_date: date = None):
        """Return the TripStop active on for_date, with gap fallback."""
        if for_date is None:
            for_date = date.today()
        if not self.stops:
            return None
        for stop in self.stops:
            if stop.start_date <= for_date <= stop.end_date:
                return stop
        # Gap fallback: most recent stop that ended before for_date
        past = [s for s in self.stops if s.end_date < for_date]
        if past:
            return past[-1]
        return self.stops[0]

    def sync_from_stops(self):
        """Sync denormalized Trip fields from stops."""
        if not self.stops:
            return
        first = self.stops[0]
        last = self.stops[-1]
        self.destination = first.destination
        self.latitude = first.latitude
        self.longitude = first.longitude
        self.start_date = first.start_date
        self.end_date = last.end_date

    def flight_for_person(self, person_id: int):
        for fi in self.flight_info:
            if fi.person_id == person_id:
                return fi
        return None


class TripPersonFlight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=False)
    outbound_flight = db.Column(db.String(100), nullable=True)
    return_flight = db.Column(db.String(100), nullable=True)

    __table_args__ = (db.UniqueConstraint("trip_id", "person_id"),)

    trip = db.relationship("Trip", backref=db.backref("flight_info", cascade="all, delete-orphan"))
    person = db.relationship("Person", backref="flight_records")

    @staticmethod
    def flight_url(flight_number: str) -> str:
        return f"https://flightaware.com/live/flight/{flight_number}"


class TripStop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)
    order = db.Column(db.Integer, nullable=False, default=0)
    destination = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    trip = db.relationship("Trip", backref=db.backref(
        "stops", cascade="all, delete-orphan", order_by="TripStop.order"
    ))


class Config(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200), nullable=False)
