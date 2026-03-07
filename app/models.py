from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

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
    abbreviation = db.Column(db.String(10), nullable=True)


class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    destination = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    outbound_flight = db.Column(db.String(100), nullable=True)
    return_flight = db.Column(db.String(100), nullable=True)
    people = db.relationship("Person", secondary=trip_person, backref="trips")

    # IATA (2-letter) → ICAO (3-letter) for US airlines.
    # FlightAware URLs require ICAO codes.
    IATA_TO_ICAO = {
        "AA": "AAL",  # American Airlines
        "DL": "DAL",  # Delta Air Lines
        "UA": "UAL",  # United Airlines
        "WN": "SWA",  # Southwest Airlines
        "B6": "JBU",  # JetBlue Airways
        "AS": "ASA",  # Alaska Airlines
        "NK": "NKS",  # Spirit Airlines
        "F9": "FFT",  # Frontier Airlines
        "HA": "HAL",  # Hawaiian Airlines
        "G4": "AAY",  # Allegiant Air
        "SY": "SCX",  # Sun Country Airlines
        "MX": "MXY",  # Breeze Airways
        "XP": "AVA",  # Avelo Airlines
    }

    @staticmethod
    def flight_url(flight_number: str) -> str:
        """Build a FlightAware URL, converting IATA airline prefixes to ICAO."""
        import re
        m = re.match(r"^([A-Z\d]{2})(\d+)$", flight_number.strip())
        if m:
            prefix, num = m.group(1), m.group(2)
            icao = Trip.IATA_TO_ICAO.get(prefix)
            if icao:
                return f"https://flightaware.com/live/flight/{icao}{num}"
        return f"https://flightaware.com/live/flight/{flight_number}"

    @property
    def display_name(self) -> str:
        return self.title if self.title else self.destination

    @property
    def is_active(self):
        today = datetime.now(ZoneInfo("America/New_York")).date()
        return self.start_date <= today <= self.end_date

    @property
    def is_upcoming(self):
        return self.start_date > datetime.now(ZoneInfo("America/New_York")).date()

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
            for_date = datetime.now(ZoneInfo("America/New_York")).date()
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
