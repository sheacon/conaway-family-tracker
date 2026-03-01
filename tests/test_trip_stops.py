from datetime import date

from freezegun import freeze_time

from app import db
from app.models import Trip, TripStop


class TestMultiStopForm:
    def test_create_multi_stop_trip(self, auth_client, app, make_person):
        p = make_person(name="Alice")
        resp = auth_client.post("/trips/new", data={
            "title": "Road Trip",
            "stop_count": "2",
            "stop_destination_0": "Nashville",
            "stop_latitude_0": "36.16",
            "stop_longitude_0": "-86.78",
            "stop_start_date_0": "2026-03-10",
            "stop_end_date_0": "2026-03-12",
            "stop_destination_1": "Memphis",
            "stop_latitude_1": "35.15",
            "stop_longitude_1": "-90.05",
            "stop_start_date_1": "2026-03-12",
            "stop_end_date_1": "2026-03-15",
            "people": [str(p.id)],
        }, follow_redirects=True)
        assert resp.status_code == 200
        trip = Trip.query.first()
        assert trip.title == "Road Trip"
        assert len(trip.stops) == 2
        assert trip.stops[0].destination == "Nashville"
        assert trip.stops[1].destination == "Memphis"
        assert trip.destination == "Nashville"
        assert trip.start_date == date(2026, 3, 10)
        assert trip.end_date == date(2026, 3, 15)

    def test_create_single_stop(self, auth_client, app, make_person):
        p = make_person(name="Bob")
        resp = auth_client.post("/trips/new", data={
            "stop_count": "1",
            "stop_destination_0": "Paris",
            "stop_latitude_0": "48.86",
            "stop_longitude_0": "2.35",
            "stop_start_date_0": "2026-04-01",
            "stop_end_date_0": "2026-04-05",
            "people": [str(p.id)],
        }, follow_redirects=True)
        assert resp.status_code == 200
        trip = Trip.query.first()
        assert len(trip.stops) == 1
        assert trip.is_multi_stop is False

    def test_missing_geocode_shows_error(self, auth_client, app):
        resp = auth_client.post("/trips/new", data={
            "stop_count": "1",
            "stop_destination_0": "Paris",
            "stop_latitude_0": "",
            "stop_longitude_0": "",
            "stop_start_date_0": "2026-04-01",
            "stop_end_date_0": "2026-04-05",
        }, follow_redirects=True)
        assert b"confirm the location" in resp.data

    def test_edit_multi_stop_trip(self, auth_client, app, make_person, make_trip, make_stop):
        p = make_person(name="Charlie")
        t = make_trip(destination="Nashville", start_date=date(2026, 3, 10),
                      end_date=date(2026, 3, 15), people=[p])
        make_stop(t, order=0, destination="Nashville",
                  start_date=date(2026, 3, 10), end_date=date(2026, 3, 15))
        resp = auth_client.post(f"/trips/{t.id}/edit", data={
            "title": "Updated Road Trip",
            "stop_count": "2",
            "stop_destination_0": "Nashville",
            "stop_latitude_0": "36.16",
            "stop_longitude_0": "-86.78",
            "stop_start_date_0": "2026-03-10",
            "stop_end_date_0": "2026-03-12",
            "stop_destination_1": "Memphis",
            "stop_latitude_1": "35.15",
            "stop_longitude_1": "-90.05",
            "stop_start_date_1": "2026-03-12",
            "stop_end_date_1": "2026-03-15",
            "people": [str(p.id)],
        }, follow_redirects=True)
        assert resp.status_code == 200
        db.session.expire_all()
        trip = db.session.get(Trip, t.id)
        assert trip.title == "Updated Road Trip"
        assert len(trip.stops) == 2
        assert trip.stops[1].destination == "Memphis"


class TestMultiStopDisplay:
    @freeze_time("2026-03-13")
    def test_current_location_uses_current_stop(self, auth_client, app,
                                                 make_person, make_trip, make_stop, make_family):
        fam = make_family(name="Test")
        p = make_person(name="Alice", family=fam)
        t = make_trip(destination="Nashville", start_date=date(2026, 3, 10),
                      end_date=date(2026, 3, 15), people=[p])
        make_stop(t, order=0, destination="Nashville", lat=36.16, lng=-86.78,
                  start_date=date(2026, 3, 10), end_date=date(2026, 3, 12))
        make_stop(t, order=1, destination="Memphis", lat=35.15, lng=-90.05,
                  start_date=date(2026, 3, 12), end_date=date(2026, 3, 15))
        resp = auth_client.get("/")
        assert resp.status_code == 200
        assert b"Memphis (Stop 2 of 2)" in resp.data

    def test_trips_page_shows_route(self, auth_client, app, make_trip, make_stop):
        t = make_trip(destination="Nashville", start_date=date(2026, 3, 10),
                      end_date=date(2026, 3, 15))
        make_stop(t, order=0, destination="Nashville",
                  start_date=date(2026, 3, 10), end_date=date(2026, 3, 12))
        make_stop(t, order=1, destination="Memphis",
                  start_date=date(2026, 3, 12), end_date=date(2026, 3, 15))
        resp = auth_client.get("/trips")
        content = resp.data.decode()
        assert "Nashville" in content
        assert "Memphis" in content
