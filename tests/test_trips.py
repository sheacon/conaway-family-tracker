"""Tests for trip routes and current location logic."""

from datetime import date
from unittest.mock import patch

from freezegun import freeze_time

from app import db
from app.models import TripStop
from tests.conftest import stop_form_data


class TestCurrentLocations:
    @freeze_time("2026-06-03 12:00:00", tz_offset=0)
    def test_person_at_home(self, app, make_person):
        from app.trips import _current_locations
        make_person(name="Alice", location_label="Chicago", lat=41.88, lng=-87.63)
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Alice")
        assert loc["traveling"] is False
        assert loc["label"] == "Chicago"
        assert loc["lat"] == 41.88

    @freeze_time("2026-06-03 12:00:00", tz_offset=0)
    def test_person_traveling(self, app, make_person, make_trip):
        from app.trips import _current_locations
        p = make_person(name="Bob")
        make_trip(destination="Paris", start_date=date(2026, 6, 1),
                  end_date=date(2026, 6, 5), people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Bob")
        assert loc["traveling"] is True
        assert loc["label"] == "Paris"

    @freeze_time("2026-06-03 08:00:00", tz_offset=0)
    def test_overlapping_trips_before_noon(self, app, make_person, make_trip):
        from app.trips import _current_locations
        p = make_person(name="Carol")
        make_trip(destination="Paris", start_date=date(2026, 6, 1),
                  end_date=date(2026, 6, 5), lat=48.85, lng=2.35, people=[p])
        make_trip(destination="London", start_date=date(2026, 6, 3),
                  end_date=date(2026, 6, 7), lat=51.51, lng=-0.13, people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Carol")
        # Before noon ET shows first trip
        assert loc["label"] == "Paris"

    @freeze_time("2026-06-03 18:00:00", tz_offset=0)
    def test_overlapping_trips_after_noon(self, app, make_person, make_trip):
        from app.trips import _current_locations
        p = make_person(name="Carol")
        make_trip(destination="Paris", start_date=date(2026, 6, 1),
                  end_date=date(2026, 6, 5), lat=48.85, lng=2.35, people=[p])
        make_trip(destination="London", start_date=date(2026, 6, 3),
                  end_date=date(2026, 6, 7), lat=51.51, lng=-0.13, people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Carol")
        # After noon ET shows last trip
        assert loc["label"] == "London"

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_travel_day_outbound(self, app, make_person, make_trip):
        from app.trips import _current_locations
        p = make_person(name="Dan", lat=40.0, lng=-90.0)
        make_trip(destination="Paris", start_date=date(2026, 6, 1),
                  end_date=date(2026, 6, 5), lat=48.0, lng=2.0, people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Dan")
        assert loc["travel_day"] is True
        # Midpoint between home and destination
        assert loc["lat"] == (40.0 + 48.0) / 2
        assert loc["lng"] == (-90.0 + 2.0) / 2

    @freeze_time("2026-06-05 12:00:00", tz_offset=0)
    def test_travel_day_return(self, app, make_person, make_trip):
        from app.trips import _current_locations
        p = make_person(name="Eve", lat=40.0, lng=-90.0)
        make_trip(destination="Paris", start_date=date(2026, 6, 1),
                  end_date=date(2026, 6, 5), lat=48.0, lng=2.0, people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Eve")
        assert loc["travel_day"] is True
        # Midpoint between destination and home
        assert loc["lat"] == (48.0 + 40.0) / 2

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_travel_day_single_day_trip(self, app, make_person, make_trip):
        from app.trips import _current_locations
        p = make_person(name="Frank", lat=40.0, lng=-90.0)
        make_trip(destination="NYC", start_date=date(2026, 6, 1),
                  end_date=date(2026, 6, 1), lat=40.7, lng=-74.0, people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Frank")
        assert loc["travel_day"] is True

    @freeze_time("2026-06-05 12:00:00", tz_offset=0)
    def test_travel_day_multi_stop_gap(self, app, make_person, make_trip, make_stop):
        from app.trips import _current_locations
        p = make_person(name="Grace", lat=40.0, lng=-90.0)
        t = make_trip(destination="Nashville", start_date=date(2026, 6, 1),
                      end_date=date(2026, 6, 10), lat=36.16, lng=-86.78, people=[p])
        make_stop(t, order=0, destination="Nashville", lat=36.16, lng=-86.78,
                  start_date=date(2026, 6, 1), end_date=date(2026, 6, 4))
        make_stop(t, order=1, destination="Memphis", lat=35.15, lng=-90.05,
                  start_date=date(2026, 6, 6), end_date=date(2026, 6, 10))
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Grace")
        assert loc["travel_day"] is True
        # Midpoint between Nashville and Memphis
        assert loc["lat"] == (36.16 + 35.15) / 2

    @freeze_time("2026-06-01 08:00:00", tz_offset=0)
    def test_flight_outbound_day(self, app, make_person, make_trip):
        from app.trips import _current_locations
        p = make_person(name="Henry")
        make_trip(destination="Paris", start_date=date(2026, 6, 1),
                  end_date=date(2026, 6, 5), outbound_flight="AA100", people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Henry")
        assert loc["flight"]["number"] == "AA100"
        assert loc["flight"]["label"] == "Outbound"

    @freeze_time("2026-06-05 12:00:00", tz_offset=0)
    def test_flight_return_day(self, app, make_person, make_trip):
        from app.trips import _current_locations
        p = make_person(name="Iris")
        make_trip(destination="Paris", start_date=date(2026, 6, 1),
                  end_date=date(2026, 6, 5), return_flight="DL200", people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Iris")
        assert loc["flight"]["number"] == "DL200"
        assert loc["flight"]["label"] == "Return"

    @freeze_time("2026-06-01 08:00:00", tz_offset=0)
    def test_flight_same_day_before_noon(self, app, make_person, make_trip):
        from app.trips import _current_locations
        p = make_person(name="Jack")
        make_trip(destination="NYC", start_date=date(2026, 6, 1),
                  end_date=date(2026, 6, 1),
                  outbound_flight="AA100", return_flight="AA200", people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Jack")
        assert loc["flight"]["number"] == "AA100"

    @freeze_time("2026-06-01 18:00:00", tz_offset=0)
    def test_flight_same_day_after_noon(self, app, make_person, make_trip):
        from app.trips import _current_locations
        p = make_person(name="Kate")
        make_trip(destination="NYC", start_date=date(2026, 6, 1),
                  end_date=date(2026, 6, 1),
                  outbound_flight="AA100", return_flight="AA200", people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Kate")
        assert loc["flight"]["number"] == "AA200"

    @freeze_time("2026-06-03 12:00:00", tz_offset=0)
    def test_no_flight_on_middle_day(self, app, make_person, make_trip):
        from app.trips import _current_locations
        p = make_person(name="Lee")
        make_trip(destination="Paris", start_date=date(2026, 6, 1),
                  end_date=date(2026, 6, 5),
                  outbound_flight="AA100", return_flight="AA200", people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Lee")
        assert loc["flight"] is None

    @freeze_time("2026-06-03 12:00:00", tz_offset=0)
    def test_multi_stop_current_stop_info(self, app, make_person, make_trip, make_stop):
        from app.trips import _current_locations
        p = make_person(name="Mia")
        t = make_trip(destination="Nashville", start_date=date(2026, 6, 1),
                      end_date=date(2026, 6, 10), people=[p])
        make_stop(t, order=0, destination="Nashville",
                  start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        make_stop(t, order=1, destination="Memphis",
                  start_date=date(2026, 6, 6), end_date=date(2026, 6, 10))
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Mia")
        assert "Nashville" in loc["stop_info"]
        assert "Stop 1 of 2" in loc["stop_info"]

    @freeze_time("2026-06-03 12:00:00", tz_offset=0)
    def test_next_trip_info(self, app, make_person, make_trip):
        from app.trips import _current_locations
        p = make_person(name="Nina")
        make_trip(destination="London", start_date=date(2026, 7, 1),
                  end_date=date(2026, 7, 5), people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Nina")
        assert loc["next_trip"] is not None
        assert loc["next_trip"]["destination"] == "London"


class TestPeopleByFamily:
    def test_groups_by_family(self, app, make_family, make_person):
        from app.trips import _people_by_family
        f1 = make_family(name="Smith", sort_order=1)
        f2 = make_family(name="Jones", sort_order=2)
        make_person(name="Alice", family=f1)
        make_person(name="Bob", family=f2)
        groups = _people_by_family()
        keys = list(groups.keys())
        assert "Smith" in keys
        assert "Jones" in keys
        assert keys.index("Smith") < keys.index("Jones")

    def test_unfamilied_in_other_group(self, app, make_person):
        from app.trips import _people_by_family
        make_person(name="Orphan")
        groups = _people_by_family()
        assert "Other" in groups


class TestDashboard:
    @freeze_time("2026-06-03 12:00:00", tz_offset=0)
    def test_requires_auth(self, client):
        resp = client.get("/")
        assert resp.status_code == 302

    @freeze_time("2026-06-03 12:00:00", tz_offset=0)
    def test_renders(self, auth_client):
        resp = auth_client.get("/")
        assert resp.status_code == 200

    @freeze_time("2026-06-03 12:00:00", tz_offset=0)
    def test_shows_upcoming_trips(self, auth_client, make_person, make_trip):
        p = make_person(name="Alice")
        make_trip(destination="Tokyo", start_date=date(2026, 6, 10),
                  end_date=date(2026, 6, 15), people=[p])
        resp = auth_client.get("/")
        assert b"Tokyo" in resp.data


class TestMapImageRoute:
    def test_requires_auth(self, client):
        resp = client.get("/map-image")
        assert resp.status_code == 302

    def test_returns_404_when_no_image(self, auth_client, tmp_path):
        with patch("app.map_generator._cache_paths",
                   return_value=(tmp_path / "nonexistent.png", tmp_path / "h")):
            resp = auth_client.get("/map-image")
        assert resp.status_code == 404

    def test_returns_image_when_cached(self, auth_client, tmp_path):
        img = tmp_path / "map_cache.png"
        img.write_bytes(b"\x89PNG fake image data")
        with patch("app.map_generator._cache_paths",
                   return_value=(img, tmp_path / "map_cache.hash")):
            resp = auth_client.get("/map-image")
        assert resp.status_code == 200


class TestTripList:
    @freeze_time("2026-06-03 12:00:00", tz_offset=0)
    def test_shows_upcoming_trips(self, auth_client, make_trip):
        make_trip(destination="Future", start_date=date(2026, 7, 1),
                  end_date=date(2026, 7, 5))
        resp = auth_client.get("/trips")
        assert b"Future" in resp.data

    @freeze_time("2026-06-03 12:00:00", tz_offset=0)
    def test_hides_past_trips_by_default(self, auth_client, make_trip):
        make_trip(destination="Past", start_date=date(2026, 5, 1),
                  end_date=date(2026, 5, 5))
        resp = auth_client.get("/trips")
        assert b"Past" not in resp.data

    @freeze_time("2026-06-03 12:00:00", tz_offset=0)
    def test_shows_past_trips_when_requested(self, auth_client, make_trip):
        make_trip(destination="Past", start_date=date(2026, 5, 1),
                  end_date=date(2026, 5, 5))
        resp = auth_client.get("/trips?show_past=1")
        assert b"Past" in resp.data

    @freeze_time("2026-06-03 12:00:00", tz_offset=0)
    def test_shows_multi_stop_route(self, auth_client, make_person, make_trip, make_stop):
        p = make_person(name="Alice")
        t = make_trip(destination="Nashville", start_date=date(2026, 6, 10),
                      end_date=date(2026, 6, 20), people=[p])
        make_stop(t, order=0, destination="Nashville",
                  start_date=date(2026, 6, 10), end_date=date(2026, 6, 15))
        make_stop(t, order=1, destination="Memphis",
                  start_date=date(2026, 6, 16), end_date=date(2026, 6, 20))
        resp = auth_client.get("/trips")
        content = resp.data.decode()
        assert "Nashville" in content


class TestNewTrip:
    def test_get_form(self, auth_client):
        resp = auth_client.get("/trips/new")
        assert resp.status_code == 200

    def test_create_single_stop(self, auth_client, make_person):
        p = make_person(name="Alice")
        data = stop_form_data("Tokyo", "2026-07-01", "2026-07-10", 35.68, 139.69)
        data["people"] = str(p.id)
        with patch("app.trips.notify_trip_created"):
            resp = auth_client.post("/trips/new", data=data)
        assert resp.status_code == 302
        from app.models import Trip
        trip = Trip.query.first()
        assert trip.destination == "Tokyo"
        assert trip.stops[0].destination == "Tokyo"

    def test_create_multi_stop(self, auth_client, make_person):
        p = make_person(name="Alice")
        data = {
            "stop_count": "2",
            "stop_destination_0": "Nashville",
            "stop_latitude_0": "36.16",
            "stop_longitude_0": "-86.78",
            "stop_start_date_0": "2026-07-01",
            "stop_end_date_0": "2026-07-05",
            "stop_destination_1": "Memphis",
            "stop_latitude_1": "35.15",
            "stop_longitude_1": "-90.05",
            "stop_start_date_1": "2026-07-06",
            "stop_end_date_1": "2026-07-10",
            "people": str(p.id),
        }
        with patch("app.trips.notify_trip_created"):
            resp = auth_client.post("/trips/new", data=data)
        assert resp.status_code == 302
        from app.models import Trip
        trip = Trip.query.first()
        assert len(trip.stops) == 2

    def test_create_with_flights(self, auth_client):
        data = stop_form_data("Paris", "2026-07-01", "2026-07-10", 48.85, 2.35)
        data["transport_mode"] = "flying"
        data["outbound_flight"] = "AA100"
        data["return_flight"] = "AA200"
        with patch("app.trips.notify_trip_created"):
            resp = auth_client.post("/trips/new", data=data)
        assert resp.status_code == 302
        from app.models import Trip
        trip = Trip.query.first()
        assert trip.outbound_flight == "AA100"
        assert trip.return_flight == "AA200"

    def test_create_with_title_and_notes(self, auth_client):
        data = stop_form_data("Cancun", "2026-07-01", "2026-07-10", 21.16, -86.85)
        data["title"] = "Spring Break"
        data["notes"] = "Don't forget sunscreen"
        with patch("app.trips.notify_trip_created"):
            resp = auth_client.post("/trips/new", data=data)
        assert resp.status_code == 302
        from app.models import Trip
        trip = Trip.query.first()
        assert trip.title == "Spring Break"
        assert trip.notes == "Don't forget sunscreen"

    def test_create_without_coords_flashes_error(self, auth_client):
        data = {
            "stop_count": "1",
            "stop_destination_0": "Nowhere",
            "stop_latitude_0": "",
            "stop_longitude_0": "",
            "stop_start_date_0": "2026-07-01",
            "stop_end_date_0": "2026-07-05",
        }
        resp = auth_client.post("/trips/new", data=data)
        assert resp.status_code == 200
        assert b"confirm the location" in resp.data

    def test_notifies_on_create(self, auth_client):
        data = stop_form_data("Paris", "2026-07-01", "2026-07-10", 48.85, 2.35)
        with patch("app.trips.notify_trip_created") as mock_notify:
            auth_client.post("/trips/new", data=data)
        mock_notify.assert_called_once()

    def test_non_flying_clears_flights(self, auth_client):
        data = stop_form_data("Denver", "2026-07-01", "2026-07-10", 39.74, -104.99)
        data["transport_mode"] = "driving"
        data["outbound_flight"] = "AA100"
        with patch("app.trips.notify_trip_created"):
            auth_client.post("/trips/new", data=data)
        from app.models import Trip
        trip = Trip.query.first()
        assert trip.outbound_flight is None


class TestEditTrip:
    def test_get_form(self, auth_client, make_trip):
        t = make_trip()
        resp = auth_client.get(f"/trips/{t.id}/edit")
        assert resp.status_code == 200

    def test_update_trip(self, auth_client, make_trip, make_stop):
        t = make_trip(destination="Old")
        make_stop(t, destination="Old")
        data = stop_form_data("New", "2026-07-01", "2026-07-10", 35.0, 139.0)
        with patch("app.trips.notify_trip_updated"):
            resp = auth_client.post(f"/trips/{t.id}/edit", data=data)
        assert resp.status_code == 302
        db.session.refresh(t)
        assert t.destination == "New"

    def test_syncs_from_stops(self, auth_client, make_trip, make_stop):
        t = make_trip(destination="Old", start_date=date(2026, 6, 1),
                      end_date=date(2026, 6, 5))
        make_stop(t, destination="Old")
        data = {
            "stop_count": "2",
            "stop_destination_0": "Nashville",
            "stop_latitude_0": "36.16",
            "stop_longitude_0": "-86.78",
            "stop_start_date_0": "2026-07-01",
            "stop_end_date_0": "2026-07-05",
            "stop_destination_1": "Memphis",
            "stop_latitude_1": "35.15",
            "stop_longitude_1": "-90.05",
            "stop_start_date_1": "2026-07-06",
            "stop_end_date_1": "2026-07-10",
        }
        with patch("app.trips.notify_trip_updated"):
            auth_client.post(f"/trips/{t.id}/edit", data=data)
        db.session.refresh(t)
        assert t.destination == "Nashville"
        assert t.end_date == date(2026, 7, 10)

    def test_notifies_on_update(self, auth_client, make_trip, make_stop):
        t = make_trip()
        make_stop(t)
        data = stop_form_data("Updated", "2026-07-01", "2026-07-10", 35.0, 139.0)
        with patch("app.trips.notify_trip_updated") as mock_notify:
            auth_client.post(f"/trips/{t.id}/edit", data=data)
        mock_notify.assert_called_once()

    def test_edit_nonexistent_returns_404(self, auth_client):
        resp = auth_client.get("/trips/9999/edit")
        assert resp.status_code == 404

    def test_replaces_stops_on_edit(self, auth_client, make_trip, make_stop):
        t = make_trip()
        make_stop(t, destination="OldStop")
        data = stop_form_data("NewStop", "2026-07-01", "2026-07-10", 35.0, 139.0)
        with patch("app.trips.notify_trip_updated"):
            auth_client.post(f"/trips/{t.id}/edit", data=data)
        stops = TripStop.query.filter_by(trip_id=t.id).all()
        assert len(stops) == 1
        assert stops[0].destination == "NewStop"


class TestDeleteTrip:
    def test_delete_trip(self, auth_client, make_trip):
        t = make_trip()
        with patch("app.trips.notify_trip_deleted"):
            resp = auth_client.post(f"/trips/{t.id}/delete")
        assert resp.status_code == 302
        from app.models import Trip
        assert Trip.query.get(t.id) is None

    def test_delete_cascades_stops(self, auth_client, make_trip, make_stop):
        t = make_trip()
        make_stop(t)
        with patch("app.trips.notify_trip_deleted"):
            auth_client.post(f"/trips/{t.id}/delete")
        assert TripStop.query.count() == 0

    def test_notifies_on_delete(self, auth_client, make_trip):
        t = make_trip()
        with patch("app.trips.notify_trip_deleted") as mock_notify:
            auth_client.post(f"/trips/{t.id}/delete")
        mock_notify.assert_called_once()

    def test_delete_nonexistent_returns_404(self, auth_client):
        resp = auth_client.post("/trips/9999/delete")
        assert resp.status_code == 404
