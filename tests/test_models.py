from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app import db
from app.models import Family, Person, Trip, TripStop, Config


class TestFamily:
    def test_create(self, app, make_family):
        fam = make_family(name="Smiths", sort_order=0)
        assert fam.id is not None
        assert fam.name == "Smiths"
        assert fam.sort_order == 0

    def test_default_sort_order(self, app):
        fam = Family(name="Test")
        db.session.add(fam)
        db.session.commit()
        assert fam.sort_order == 0

    def test_unique_name(self, app, make_family):
        make_family(name="Unique")
        with pytest.raises(Exception):
            make_family(name="Unique")


class TestPerson:
    def test_create(self, app, make_person):
        p = make_person(name="Alice")
        assert p.id is not None
        assert p.name == "Alice"
        assert p.default_location_label == "Home"
        assert p.default_location_lat == 39.8283

    def test_defaults(self, app):
        p = Person(name="Bob")
        db.session.add(p)
        db.session.commit()
        assert p.email is None
        assert p.family_id is None
        assert p.color == "#3388ff"

    def test_unique_name(self, app, make_person):
        make_person(name="Dupe")
        with pytest.raises(Exception):
            make_person(name="Dupe")

    def test_family_relationship(self, app, make_family, make_person):
        fam = make_family(name="Joneses")
        p = make_person(name="Jim", family=fam)
        assert p.family.name == "Joneses"
        assert p in fam.members

    def test_no_family(self, app, make_person):
        p = make_person(name="Solo")
        assert p.family is None


class TestTrip:
    def test_create(self, app, make_trip):
        t = make_trip(destination="Rome")
        assert t.id is not None
        assert t.destination == "Rome"

    @freeze_time("2026-03-03 12:00:00")
    def test_is_active_in_range(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        assert t.is_active is True

    @freeze_time("2026-03-01 12:00:00")
    def test_is_active_on_start(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        assert t.is_active is True

    @freeze_time("2026-03-05 12:00:00")
    def test_is_active_on_end(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        assert t.is_active is True

    @freeze_time("2026-02-28 12:00:00")
    def test_is_active_before_start(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        assert t.is_active is False

    @freeze_time("2026-03-06 12:00:00")
    def test_is_active_after_end(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        assert t.is_active is False

    @freeze_time("2026-02-28 12:00:00")
    def test_is_upcoming(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        assert t.is_upcoming is True

    @freeze_time("2026-03-01 12:00:00")
    def test_is_upcoming_false_on_start(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        assert t.is_upcoming is False

    def test_display_name_with_title(self, app, make_trip):
        t = make_trip(destination="Paris", title="Spring Break")
        assert t.display_name == "Spring Break"

    def test_display_name_without_title(self, app, make_trip):
        t = make_trip(destination="Paris")
        assert t.display_name == "Paris"

    def test_title_and_notes_nullable(self, app, make_trip):
        t = make_trip(destination="Rome")
        assert t.title is None
        assert t.notes is None

    def test_title_and_notes_stored(self, app, make_trip):
        t = make_trip(destination="Tokyo", title="Asia Trip", notes="Pack light")
        assert t.title == "Asia Trip"
        assert t.notes == "Pack light"

    def test_people_many_to_many(self, app, make_trip, make_person):
        p1 = make_person(name="A")
        p2 = make_person(name="B")
        t = make_trip(people=[p1, p2])
        assert len(t.people) == 2
        assert t in p1.trips

    def test_empty_people(self, app, make_trip):
        t = make_trip()
        assert t.people == []

    @freeze_time("2026-03-01 12:00:00")
    def test_single_day_trip_active(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 1))
        assert t.is_active is True

    def test_flights_stored(self, app, make_trip):
        t = make_trip(outbound_flight="BA100", return_flight="BA101")
        assert t.outbound_flight == "BA100"
        assert t.return_flight == "BA101"

    def test_flights_nullable(self, app, make_trip):
        t = make_trip()
        assert t.outbound_flight is None
        assert t.return_flight is None

    @freeze_time("2026-03-05 03:00:00", tz_offset=0)
    def test_is_active_uses_et_not_utc(self, app, make_trip):
        """At 3 AM UTC Mar 5 (10 PM ET Mar 4), a trip starting Mar 5 should NOT be active."""
        t = make_trip(start_date=date(2026, 3, 5), end_date=date(2026, 3, 10))
        assert t.is_active is False

    @freeze_time("2026-03-05 03:00:00", tz_offset=0)
    def test_is_upcoming_uses_et_not_utc(self, app, make_trip):
        """At 3 AM UTC Mar 5 (10 PM ET Mar 4), a trip starting Mar 5 should be upcoming."""
        t = make_trip(start_date=date(2026, 3, 5), end_date=date(2026, 3, 10))
        assert t.is_upcoming is True

    @freeze_time("2026-03-11 03:00:00", tz_offset=0)
    def test_is_active_not_ended_early_in_et(self, app, make_trip):
        """At 3 AM UTC Mar 11 (10 PM ET Mar 10), a trip ending Mar 10 should still be active."""
        t = make_trip(start_date=date(2026, 3, 5), end_date=date(2026, 3, 10))
        assert t.is_active is True


class TestFlightUrl:
    def test_iata_to_icao_conversion(self, app):
        assert Trip.flight_url("UA123") == "https://flightaware.com/live/flight/UAL123"
        assert Trip.flight_url("DL1462") == "https://flightaware.com/live/flight/DAL1462"
        assert Trip.flight_url("WN209") == "https://flightaware.com/live/flight/SWA209"
        assert Trip.flight_url("AA100") == "https://flightaware.com/live/flight/AAL100"
        assert Trip.flight_url("B6800") == "https://flightaware.com/live/flight/JBU800"

    def test_icao_passthrough(self, app):
        assert Trip.flight_url("UAL123") == "https://flightaware.com/live/flight/UAL123"

    def test_unknown_prefix_passthrough(self, app):
        assert Trip.flight_url("ZZ999") == "https://flightaware.com/live/flight/ZZ999"


class TestTripStop:
    def test_create(self, app, make_trip, make_stop):
        t = make_trip(start_date=date(2026, 3, 10), end_date=date(2026, 3, 15))
        s = make_stop(t, order=0, destination="Nashville",
                      start_date=date(2026, 3, 10), end_date=date(2026, 3, 12))
        assert s.id is not None
        assert s.trip_id == t.id

    def test_cascade_delete(self, app, make_trip, make_stop):
        t = make_trip(start_date=date(2026, 3, 10), end_date=date(2026, 3, 15))
        make_stop(t, order=0, start_date=date(2026, 3, 10), end_date=date(2026, 3, 12))
        make_stop(t, order=1, destination="Memphis",
                  start_date=date(2026, 3, 12), end_date=date(2026, 3, 15))
        db.session.delete(t)
        db.session.commit()
        assert TripStop.query.count() == 0

    def test_stops_ordered(self, app, make_trip, make_stop):
        t = make_trip(start_date=date(2026, 3, 10), end_date=date(2026, 3, 15))
        make_stop(t, order=1, destination="Memphis",
                  start_date=date(2026, 3, 12), end_date=date(2026, 3, 15))
        make_stop(t, order=0, destination="Nashville",
                  start_date=date(2026, 3, 10), end_date=date(2026, 3, 12))
        db.session.expire_all()
        assert t.stops[0].destination == "Nashville"
        assert t.stops[1].destination == "Memphis"

    def test_is_multi_stop(self, app, make_trip, make_stop):
        t = make_trip(start_date=date(2026, 3, 10), end_date=date(2026, 3, 15))
        make_stop(t, order=0, start_date=date(2026, 3, 10), end_date=date(2026, 3, 12))
        make_stop(t, order=1, destination="Memphis",
                  start_date=date(2026, 3, 12), end_date=date(2026, 3, 15))
        db.session.expire_all()
        assert t.is_multi_stop is True

    def test_single_stop_not_multi(self, app, make_trip, make_stop):
        t = make_trip(start_date=date(2026, 3, 10), end_date=date(2026, 3, 15))
        make_stop(t)
        db.session.expire_all()
        assert t.is_multi_stop is False

    def test_destinations_summary_multi(self, app, make_trip, make_stop):
        t = make_trip(destination="Nashville", start_date=date(2026, 3, 10),
                      end_date=date(2026, 3, 15))
        make_stop(t, order=0, destination="Nashville",
                  start_date=date(2026, 3, 10), end_date=date(2026, 3, 11))
        make_stop(t, order=1, destination="Memphis",
                  start_date=date(2026, 3, 11), end_date=date(2026, 3, 14))
        make_stop(t, order=2, destination="Nashville",
                  start_date=date(2026, 3, 14), end_date=date(2026, 3, 15))
        db.session.expire_all()
        assert t.destinations_summary == "Nashville → Memphis → Nashville"

    def test_destinations_summary_dedup_consecutive(self, app, make_trip, make_stop):
        t = make_trip(start_date=date(2026, 3, 10), end_date=date(2026, 3, 15))
        make_stop(t, order=0, destination="Nashville",
                  start_date=date(2026, 3, 10), end_date=date(2026, 3, 12))
        make_stop(t, order=1, destination="Nashville",
                  start_date=date(2026, 3, 12), end_date=date(2026, 3, 15))
        db.session.expire_all()
        assert t.destinations_summary == "Nashville"

    def test_destinations_summary_no_stops(self, app, make_trip):
        t = make_trip(destination="Paris")
        assert t.destinations_summary == "Paris"

    def test_current_stop_active(self, app, make_trip, make_stop):
        t = make_trip(start_date=date(2026, 3, 10), end_date=date(2026, 3, 15))
        make_stop(t, order=0, destination="Nashville",
                  start_date=date(2026, 3, 10), end_date=date(2026, 3, 12))
        make_stop(t, order=1, destination="Memphis",
                  start_date=date(2026, 3, 12), end_date=date(2026, 3, 15))
        db.session.expire_all()
        assert t.current_stop(date(2026, 3, 11)).destination == "Nashville"
        assert t.current_stop(date(2026, 3, 13)).destination == "Memphis"

    def test_current_stop_gap_fallback(self, app, make_trip, make_stop):
        t = make_trip(start_date=date(2026, 3, 10), end_date=date(2026, 3, 15))
        make_stop(t, order=0, destination="Nashville",
                  start_date=date(2026, 3, 10), end_date=date(2026, 3, 11))
        make_stop(t, order=1, destination="Memphis",
                  start_date=date(2026, 3, 13), end_date=date(2026, 3, 15))
        db.session.expire_all()
        assert t.current_stop(date(2026, 3, 12)).destination == "Nashville"

    def test_current_stop_no_stops(self, app, make_trip):
        t = make_trip()
        assert t.current_stop(date(2026, 3, 3)) is None

    def test_sync_from_stops(self, app, make_trip, make_stop):
        t = make_trip(destination="Old", lat=0.0, lng=0.0,
                      start_date=date(2026, 1, 1), end_date=date(2026, 1, 1))
        make_stop(t, order=0, destination="Nashville", lat=36.16, lng=-86.78,
                  start_date=date(2026, 3, 10), end_date=date(2026, 3, 12))
        make_stop(t, order=1, destination="Memphis", lat=35.15, lng=-90.05,
                  start_date=date(2026, 3, 12), end_date=date(2026, 3, 15))
        db.session.expire_all()
        t.sync_from_stops()
        assert t.destination == "Nashville"
        assert t.latitude == 36.16
        assert t.start_date == date(2026, 3, 10)
        assert t.end_date == date(2026, 3, 15)


class TestConfig:
    def test_key_value(self, app):
        c = Config(key="test_key", value="test_val")
        db.session.add(c)
        db.session.commit()
        assert db.session.get(Config, "test_key").value == "test_val"
