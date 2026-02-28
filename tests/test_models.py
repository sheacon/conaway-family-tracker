from datetime import date

import pytest
from freezegun import freeze_time

from app import db
from app.models import Family, Person, Trip, Config, TripPersonFlight


class TestFamily:
    def test_create_family(self, app, make_family):
        fam = make_family(name="Smiths", sort_order=0)
        assert fam.id is not None
        assert fam.name == "Smiths"
        assert fam.sort_order == 0

    def test_family_default_sort_order(self, app, make_family):
        fam = Family(name="Test")
        db.session.add(fam)
        db.session.commit()
        assert fam.sort_order == 0

    def test_family_unique_name(self, app, make_family):
        make_family(name="Unique")
        with pytest.raises(Exception):
            make_family(name="Unique")


class TestPerson:
    def test_create_person(self, app, make_person):
        p = make_person(name="Alice")
        assert p.id is not None
        assert p.name == "Alice"
        assert p.default_location_label == "Home"
        assert p.default_location_lat == 39.8283
        assert p.default_location_lng == -98.5795
        assert p.color == "#3388ff"

    def test_person_defaults(self, app):
        p = Person(name="Bob")
        db.session.add(p)
        db.session.commit()
        assert p.email is None
        assert p.family_id is None

    def test_person_unique_name(self, app, make_person):
        make_person(name="Dupe")
        with pytest.raises(Exception):
            make_person(name="Dupe")

    def test_person_family_relationship(self, app, make_family, make_person):
        fam = make_family(name="Joneses")
        p = make_person(name="Jim", family=fam)
        assert p.family.name == "Joneses"
        assert p in fam.members

    def test_person_no_family(self, app, make_person):
        p = make_person(name="Solo")
        assert p.family is None


class TestTrip:
    def test_create_trip(self, app, make_trip):
        t = make_trip(destination="Rome")
        assert t.id is not None
        assert t.destination == "Rome"

    @freeze_time("2026-03-03")
    def test_is_active_in_range(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        assert t.is_active is True

    @freeze_time("2026-03-01")
    def test_is_active_on_start(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        assert t.is_active is True

    @freeze_time("2026-03-05")
    def test_is_active_on_end(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        assert t.is_active is True

    @freeze_time("2026-02-28")
    def test_is_active_before_start(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        assert t.is_active is False

    @freeze_time("2026-03-06")
    def test_is_active_after_end(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        assert t.is_active is False

    @freeze_time("2026-02-28")
    def test_is_upcoming_future(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        assert t.is_upcoming is True

    @freeze_time("2026-03-01")
    def test_is_upcoming_today(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        assert t.is_upcoming is False

    @freeze_time("2026-03-06")
    def test_is_upcoming_past(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        assert t.is_upcoming is False

    def test_trip_people_many_to_many(self, app, make_trip, make_person):
        p1 = make_person(name="A")
        p2 = make_person(name="B")
        t = make_trip(people=[p1, p2])
        assert len(t.people) == 2
        assert t in p1.trips

    def test_trip_empty_people(self, app, make_trip):
        t = make_trip()
        assert t.people == []

    @freeze_time("2026-03-01")
    def test_single_day_trip_active(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 1))
        assert t.is_active is True

    def test_display_name_with_title(self, app, make_trip):
        t = make_trip(destination="Paris", title="Spring Break 2026")
        assert t.display_name == "Spring Break 2026"

    def test_display_name_without_title(self, app, make_trip):
        t = make_trip(destination="Paris")
        assert t.display_name == "Paris"

    def test_title_nullable(self, app, make_trip):
        t = make_trip(destination="Rome")
        assert t.title is None

    def test_notes_nullable(self, app, make_trip):
        t = make_trip(destination="Rome")
        assert t.notes is None

    def test_title_and_notes_stored(self, app, make_trip):
        t = make_trip(destination="Tokyo", title="Asia Trip", notes="Flight at 9am")
        assert t.title == "Asia Trip"
        assert t.notes == "Flight at 9am"


class TestTripPersonFlight:
    def test_create_flight(self, app, make_person, make_trip, make_flight):
        p = make_person(name="Flyer")
        t = make_trip(destination="Rome", people=[p])
        f = make_flight(t, p, outbound="UA123", ret="UA456")
        assert f.id is not None
        assert f.outbound_flight == "UA123"
        assert f.return_flight == "UA456"

    def test_flight_url(self, app):
        assert TripPersonFlight.flight_url("UA123") == "https://flightaware.com/live/flight/UA123"

    def test_cascade_delete(self, app, make_person, make_trip, make_flight):
        p = make_person(name="Cascade")
        t = make_trip(destination="Berlin", people=[p])
        make_flight(t, p, outbound="DL100")
        db.session.delete(t)
        db.session.commit()
        assert TripPersonFlight.query.count() == 0

    def test_unique_constraint(self, app, make_person, make_trip, make_flight):
        p = make_person(name="Unique")
        t = make_trip(destination="Tokyo", people=[p])
        make_flight(t, p, outbound="AA1")
        with pytest.raises(Exception):
            make_flight(t, p, outbound="AA2")

    def test_flight_for_person(self, app, make_person, make_trip, make_flight):
        p1 = make_person(name="P1")
        p2 = make_person(name="P2")
        t = make_trip(destination="Paris", people=[p1, p2])
        make_flight(t, p1, outbound="AF100")
        assert t.flight_for_person(p1.id).outbound_flight == "AF100"
        assert t.flight_for_person(p2.id) is None

    def test_flight_nullable_fields(self, app, make_person, make_trip, make_flight):
        p = make_person(name="Partial")
        t = make_trip(destination="Madrid", people=[p])
        f = make_flight(t, p, outbound="IB200")
        assert f.outbound_flight == "IB200"
        assert f.return_flight is None


class TestConfig:
    def test_config_key_value(self, app):
        c = Config(key="test_key", value="test_val")
        db.session.add(c)
        db.session.commit()
        assert Config.query.get("test_key").value == "test_val"
