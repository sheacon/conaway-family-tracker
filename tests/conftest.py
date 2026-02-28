import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["APP_PASSWORD"] = "testpass"
os.environ["RESEND_API_KEY"] = "test-key"
os.environ["RESEND_FROM_EMAIL"] = "test@example.com"

import pytest

from app import db as _db
from app import create_app
from app.models import Family, Person, Trip, TripPersonFlight


@pytest.fixture()
def app():
    application = create_app()
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(app):
    c = app.test_client()
    c.post("/login", data={"password": "testpass"})
    return c


@pytest.fixture()
def make_family(app):
    _counter = [0]

    def _make(name=None, sort_order=None):
        _counter[0] += 1
        if name is None:
            name = f"Family {_counter[0]}"
        if sort_order is None:
            sort_order = _counter[0]
        fam = Family(name=name, sort_order=sort_order)
        _db.session.add(fam)
        _db.session.commit()
        return fam

    return _make


@pytest.fixture()
def make_person(app):
    _counter = [0]

    def _make(name=None, email=None, family=None, color="#3388ff",
              location_label="Home", lat=39.8283, lng=-98.5795):
        _counter[0] += 1
        if name is None:
            name = f"Person {_counter[0]}"
        p = Person(
            name=name,
            email=email,
            color=color,
            default_location_label=location_label,
            default_location_lat=lat,
            default_location_lng=lng,
        )
        if family:
            p.family_id = family.id
        _db.session.add(p)
        _db.session.commit()
        return p

    return _make


@pytest.fixture()
def make_trip(app):
    from datetime import date

    def _make(destination="Paris", start_date=None, end_date=None,
              lat=48.8566, lng=2.3522, people=None, title=None, notes=None):
        if start_date is None:
            start_date = date(2026, 3, 1)
        if end_date is None:
            end_date = date(2026, 3, 5)
        t = Trip(
            destination=destination,
            title=title,
            notes=notes,
            start_date=start_date,
            end_date=end_date,
            latitude=lat,
            longitude=lng,
        )
        if people:
            t.people = people
        _db.session.add(t)
        _db.session.commit()
        return t

    return _make


@pytest.fixture()
def make_flight(app):
    def _make(trip, person, outbound=None, ret=None):
        f = TripPersonFlight(
            trip_id=trip.id, person_id=person.id,
            outbound_flight=outbound, return_flight=ret,
        )
        _db.session.add(f)
        _db.session.commit()
        return f

    return _make
