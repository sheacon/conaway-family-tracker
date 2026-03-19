"""Tests for SQLAlchemy models."""

from datetime import date

from freezegun import freeze_time

from app import db
from app.models import Config, Family, Person, Trip, TripStop


class TestFamily:
    def test_create(self, make_family):
        f = make_family(name="Smith", sort_order=1)
        assert f.id is not None
        assert f.name == "Smith"
        assert f.sort_order == 1

    def test_members_relationship(self, make_family, make_person):
        f = make_family(name="Smith")
        p = make_person(name="John", family=f)
        assert p in f.members
        assert p.family == f


class TestPerson:
    def test_create(self, make_person):
        p = make_person(name="Alice", email="alice@example.com")
        assert p.id is not None
        assert p.name == "Alice"
        assert p.email == "alice@example.com"

    def test_default_location(self, make_person):
        p = make_person()
        assert p.default_location_label == "Home"
        assert p.default_location_lat == 39.8283
        assert p.default_location_lng == -98.5795

    def test_get_enabled_notifications_defaults_all(self, make_person):
        p = make_person()
        enabled = p.get_enabled_notifications()
        assert "trip_created" in enabled
        assert "trip_updated" in enabled
        assert "trip_deleted" in enabled
        assert "trip_starting_soon" in enabled
        assert "trip_started" in enabled
        assert "trip_ended" in enabled

    def test_set_and_get_notifications(self, make_person):
        p = make_person()
        p.set_enabled_notifications(["trip_created", "trip_started"])
        db.session.commit()
        enabled = p.get_enabled_notifications()
        assert enabled == {"trip_created", "trip_started"}

    def test_set_empty_notifications(self, make_person):
        p = make_person()
        p.set_enabled_notifications([])
        db.session.commit()
        assert p.get_enabled_notifications() == set()


class TestTrip:
    def test_create(self, make_trip):
        t = make_trip(destination="Tokyo")
        assert t.id is not None
        assert t.destination == "Tokyo"

    def test_display_name_with_title(self, make_trip):
        t = make_trip(title="Spring Break", destination="Cancun")
        assert t.display_name == "Spring Break"

    def test_display_name_without_title(self, make_trip):
        t = make_trip(destination="Cancun")
        assert t.display_name == "Cancun"

    @freeze_time("2026-06-03", tz_offset=0)
    def test_is_active_during_trip(self, make_trip):
        t = make_trip(start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        assert t.is_active is True

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_is_active_on_start_date(self, make_trip):
        t = make_trip(start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        assert t.is_active is True

    @freeze_time("2026-06-05 12:00:00", tz_offset=0)
    def test_is_active_on_end_date(self, make_trip):
        t = make_trip(start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        assert t.is_active is True

    @freeze_time("2026-05-31 12:00:00", tz_offset=0)
    def test_is_active_before_trip(self, make_trip):
        t = make_trip(start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        assert t.is_active is False

    @freeze_time("2026-06-06 12:00:00", tz_offset=0)
    def test_is_active_after_trip(self, make_trip):
        t = make_trip(start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        assert t.is_active is False

    @freeze_time("2026-05-31 12:00:00", tz_offset=0)
    def test_is_upcoming(self, make_trip):
        t = make_trip(start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        assert t.is_upcoming is True

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_is_not_upcoming_on_start(self, make_trip):
        t = make_trip(start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        assert t.is_upcoming is False

    def test_people_relationship(self, make_trip, make_person):
        p1 = make_person(name="A")
        p2 = make_person(name="B")
        t = make_trip(people=[p1, p2])
        assert p1 in t.people
        assert p2 in t.people
        assert t in p1.trips

    def test_transport_modes(self):
        assert "flying" in Trip.TRANSPORT_MODES
        assert "driving" in Trip.TRANSPORT_MODES
        assert "train" in Trip.TRANSPORT_MODES
        assert "boat" in Trip.TRANSPORT_MODES


class TestFlightUrl:
    def test_iata_to_icao_conversion(self):
        assert Trip.flight_url("AA100") == "https://flightaware.com/live/flight/AAL100"
        assert Trip.flight_url("DL456") == "https://flightaware.com/live/flight/DAL456"
        assert Trip.flight_url("UA789") == "https://flightaware.com/live/flight/UAL789"
        assert Trip.flight_url("WN1234") == "https://flightaware.com/live/flight/SWA1234"

    def test_unknown_airline_passthrough(self):
        assert Trip.flight_url("ZZ999") == "https://flightaware.com/live/flight/ZZ999"

    def test_already_icao(self):
        assert Trip.flight_url("AAL100") == "https://flightaware.com/live/flight/AAL100"

    def test_strips_whitespace(self):
        assert Trip.flight_url("  AA100  ") == "https://flightaware.com/live/flight/AAL100"


class TestTripStop:
    def test_create(self, make_trip, make_stop):
        t = make_trip()
        s = make_stop(t, destination="Nashville", order=0)
        assert s.id is not None
        assert s.trip_id == t.id
        assert s.destination == "Nashville"

    def test_stops_ordered(self, make_trip, make_stop):
        t = make_trip(start_date=date(2026, 6, 1), end_date=date(2026, 6, 10))
        make_stop(t, order=1, destination="Memphis",
                  start_date=date(2026, 6, 5), end_date=date(2026, 6, 10))
        make_stop(t, order=0, destination="Nashville",
                  start_date=date(2026, 6, 1), end_date=date(2026, 6, 4))
        assert t.stops[0].destination == "Nashville"
        assert t.stops[1].destination == "Memphis"

    def test_cascade_delete(self, make_trip, make_stop):
        t = make_trip()
        make_stop(t, destination="Nashville")
        db.session.delete(t)
        db.session.commit()
        assert TripStop.query.count() == 0


class TestMultiStop:
    def test_is_multi_stop_false_for_no_stops(self, make_trip):
        t = make_trip()
        assert t.is_multi_stop is False

    def test_is_multi_stop_false_for_one_stop(self, make_trip, make_stop):
        t = make_trip()
        make_stop(t)
        assert t.is_multi_stop is False

    def test_is_multi_stop_true_for_two_stops(self, make_trip, make_stop):
        t = make_trip(start_date=date(2026, 6, 1), end_date=date(2026, 6, 10))
        make_stop(t, order=0, start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        make_stop(t, order=1, destination="Memphis",
                  start_date=date(2026, 6, 6), end_date=date(2026, 6, 10))
        assert t.is_multi_stop is True

    def test_destinations_summary(self, make_trip, make_stop):
        t = make_trip(start_date=date(2026, 6, 1), end_date=date(2026, 6, 10))
        make_stop(t, order=0, destination="Nashville",
                  start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        make_stop(t, order=1, destination="Memphis",
                  start_date=date(2026, 6, 6), end_date=date(2026, 6, 10))
        assert t.destinations_summary == "Nashville \u2192 Memphis"

    def test_destinations_summary_deduplicates_consecutive(self, make_trip, make_stop):
        t = make_trip(start_date=date(2026, 6, 1), end_date=date(2026, 6, 15))
        make_stop(t, order=0, destination="Nashville",
                  start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        make_stop(t, order=1, destination="Nashville",
                  start_date=date(2026, 6, 6), end_date=date(2026, 6, 10))
        make_stop(t, order=2, destination="Memphis",
                  start_date=date(2026, 6, 11), end_date=date(2026, 6, 15))
        assert t.destinations_summary == "Nashville \u2192 Memphis"

    def test_destinations_summary_no_stops(self, make_trip):
        t = make_trip(destination="Paris")
        assert t.destinations_summary == "Paris"

    def test_current_stop_exact_date(self, make_trip, make_stop):
        t = make_trip(start_date=date(2026, 6, 1), end_date=date(2026, 6, 10))
        s1 = make_stop(t, order=0, destination="Nashville",
                       start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        make_stop(t, order=1, destination="Memphis",
                  start_date=date(2026, 6, 6), end_date=date(2026, 6, 10))
        assert t.current_stop(date(2026, 6, 3)) == s1

    def test_current_stop_gap_fallback(self, make_trip, make_stop):
        t = make_trip(start_date=date(2026, 6, 1), end_date=date(2026, 6, 12))
        s1 = make_stop(t, order=0, destination="Nashville",
                       start_date=date(2026, 6, 1), end_date=date(2026, 6, 4))
        make_stop(t, order=1, destination="Memphis",
                  start_date=date(2026, 6, 7), end_date=date(2026, 6, 12))
        # June 5 is in the gap — should fall back to most recent ended stop
        assert t.current_stop(date(2026, 6, 5)) == s1

    def test_current_stop_before_all_stops(self, make_trip, make_stop):
        t = make_trip(start_date=date(2026, 6, 3), end_date=date(2026, 6, 10))
        s1 = make_stop(t, order=0, destination="Nashville",
                       start_date=date(2026, 6, 3), end_date=date(2026, 6, 10))
        assert t.current_stop(date(2026, 6, 1)) == s1

    def test_current_stop_no_stops(self, make_trip):
        t = make_trip()
        assert t.current_stop(date(2026, 6, 3)) is None

    def test_sync_from_stops(self, make_trip, make_stop):
        t = make_trip(destination="Old", start_date=date(2026, 6, 1),
                      end_date=date(2026, 6, 5), lat=0, lng=0)
        make_stop(t, order=0, destination="Nashville", lat=36.16, lng=-86.78,
                  start_date=date(2026, 6, 1), end_date=date(2026, 6, 3))
        make_stop(t, order=1, destination="Memphis", lat=35.15, lng=-90.05,
                  start_date=date(2026, 6, 4), end_date=date(2026, 6, 8))
        t.sync_from_stops()
        assert t.destination == "Nashville"
        assert t.latitude == 36.16
        assert t.longitude == -86.78
        assert t.start_date == date(2026, 6, 1)
        assert t.end_date == date(2026, 6, 8)


class TestConfig:
    def test_create(self, app):
        c = Config(key="test_key", value="test_value")
        db.session.add(c)
        db.session.commit()
        assert db.session.get(Config, "test_key").value == "test_value"
