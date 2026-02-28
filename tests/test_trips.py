from collections import OrderedDict
from datetime import date
from unittest.mock import patch

from freezegun import freeze_time


def _stop_form_data(destination, start_date, end_date, lat, lng, **extra):
    """Helper: build form data for a single-stop trip."""
    data = {
        "stop_count": "1",
        "stop_destination_0": destination,
        "stop_latitude_0": str(lat),
        "stop_longitude_0": str(lng),
        "stop_start_date_0": start_date,
        "stop_end_date_0": end_date,
    }
    data.update(extra)
    return data


class TestDashboard:
    def test_empty_state(self, auth_client):
        resp = auth_client.get("/")
        assert resp.status_code == 200

    def test_person_default_location(self, auth_client, make_person):
        make_person(name="Alice", location_label="NYC", lat=40.7, lng=-74.0)
        resp = auth_client.get("/")
        assert b"Alice" in resp.data
        assert b"NYC" in resp.data

    @freeze_time("2026-03-03")
    def test_active_trip_location(self, auth_client, make_person, make_trip):
        p = make_person(name="Bob")
        make_trip(destination="Tokyo", start_date=date(2026, 3, 1),
                  end_date=date(2026, 3, 5), people=[p])
        resp = auth_client.get("/")
        assert b"Tokyo" in resp.data

    @freeze_time("2026-02-28")
    def test_upcoming_trips_shown(self, auth_client, make_person, make_trip):
        p = make_person(name="Carol")
        make_trip(destination="London", start_date=date(2026, 3, 10),
                  end_date=date(2026, 3, 15), people=[p])
        resp = auth_client.get("/")
        assert b"London" in resp.data

    @freeze_time("2026-02-28")
    def test_upcoming_trips_show_title_and_notes(self, auth_client, make_person, make_trip):
        p = make_person(name="Eve")
        make_trip(destination="Paris", title="Spring Break", notes="Hotel Marais",
                  start_date=date(2026, 3, 10), end_date=date(2026, 3, 15), people=[p])
        resp = auth_client.get("/")
        assert b"Spring Break" in resp.data
        assert b"Paris" in resp.data
        assert b"Hotel Marais" in resp.data

    @freeze_time("2026-04-01")
    def test_past_trips_hidden_from_upcoming(self, auth_client, make_person, make_trip):
        p = make_person(name="Dave")
        make_trip(destination="Mars", start_date=date(2026, 3, 1),
                  end_date=date(2026, 3, 5), people=[p])
        resp = auth_client.get("/")
        # Past trip should not appear in upcoming section
        assert b"Mars" not in resp.data or b"upcoming" not in resp.data.lower()

    def test_family_grouping(self, auth_client, make_family, make_person):
        fam = make_family(name="Smiths", sort_order=0)
        make_person(name="John", family=fam)
        resp = auth_client.get("/")
        assert b"Smiths" in resp.data

    def test_unfamilied_in_other(self, auth_client, make_person):
        make_person(name="Orphan")
        resp = auth_client.get("/")
        assert b"Other" in resp.data


class TestCurrentLocations:
    @freeze_time("2026-03-03")
    def test_no_active_trip(self, app, make_person):
        from app.trips import _current_locations
        make_person(name="Zara", location_label="Home", lat=1.0, lng=2.0)
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Zara")
        assert loc["label"] == "Home"
        assert loc["traveling"] is False

    @freeze_time("2026-03-03")
    def test_active_trip(self, app, make_person, make_trip):
        from app.trips import _current_locations
        p = make_person(name="Yuri")
        make_trip(destination="Berlin", start_date=date(2026, 3, 1),
                  end_date=date(2026, 3, 5), people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Yuri")
        assert loc["label"] == "Berlin"
        assert loc["traveling"] is True

    @freeze_time("2026-03-03 15:00:00", tz_offset=0)
    def test_overlapping_trips_before_noon_et(self, app, make_person, make_trip):
        """10 AM ET (15:00 UTC in Feb/EST) -> picks first trip."""
        from app.trips import _current_locations
        p = make_person(name="Xena")
        make_trip(destination="Trip1", start_date=date(2026, 3, 1),
                  end_date=date(2026, 3, 5), people=[p])
        make_trip(destination="Trip2", start_date=date(2026, 3, 2),
                  end_date=date(2026, 3, 5), people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Xena")
        assert loc["label"] == "Trip1"

    @freeze_time("2026-03-03 19:00:00", tz_offset=0)
    def test_overlapping_trips_after_noon_et(self, app, make_person, make_trip):
        """2 PM ET (19:00 UTC in Feb/EST) -> picks last trip."""
        from app.trips import _current_locations
        p = make_person(name="Wendy")
        make_trip(destination="TripA", start_date=date(2026, 3, 1),
                  end_date=date(2026, 3, 5), people=[p])
        make_trip(destination="TripB", start_date=date(2026, 3, 2),
                  end_date=date(2026, 3, 5), people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Wendy")
        assert loc["label"] == "TripB"

    @freeze_time("2026-03-03")
    def test_next_trip_formatting(self, app, make_person, make_trip):
        from app.trips import _current_locations
        p = make_person(name="Victor")
        make_trip(destination="Future", start_date=date(2026, 4, 1),
                  end_date=date(2026, 4, 5), people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Victor")
        assert loc["next_trip"]["display_name"] == "Future"
        assert loc["next_trip"]["destination"] == "Future"
        assert "Apr" in loc["next_trip"]["dates"]

    @freeze_time("2026-03-03")
    def test_next_trip_with_title(self, app, make_person, make_trip):
        from app.trips import _current_locations
        p = make_person(name="Vera")
        make_trip(destination="Tokyo", title="Japan Trip", notes="ANA flight",
                  start_date=date(2026, 4, 1), end_date=date(2026, 4, 5), people=[p])
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Vera")
        assert loc["next_trip"]["display_name"] == "Japan Trip"
        assert loc["next_trip"]["destination"] == "Tokyo"
        assert loc["next_trip"]["title"] == "Japan Trip"
        assert loc["next_trip"]["notes"] == "ANA flight"

    @freeze_time("2026-03-03")
    def test_color_and_family_passthrough(self, app, make_family, make_person):
        from app.trips import _current_locations
        fam = make_family(name="TestFam", sort_order=1)
        make_person(name="Tina", color="#ff0000", family=fam)
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "Tina")
        assert loc["color"] == "#ff0000"
        assert loc["family"] == "TestFam"


class TestPeopleByFamily:
    def test_ordering(self, app, make_family, make_person):
        from app.trips import _people_by_family
        fam1 = make_family(name="AAA", sort_order=0)
        fam2 = make_family(name="ZZZ", sort_order=1)
        make_person(name="P1", family=fam1)
        make_person(name="P2", family=fam2)
        groups = _people_by_family()
        keys = list(groups.keys())
        assert keys.index("AAA") < keys.index("ZZZ")

    def test_no_family_goes_to_other(self, app, make_person):
        from app.trips import _people_by_family
        make_person(name="Loner")
        groups = _people_by_family()
        assert "Other" in groups

    def test_returns_ordered_dict(self, app, make_person):
        from app.trips import _people_by_family
        make_person(name="Solo")
        groups = _people_by_family()
        assert isinstance(groups, OrderedDict)


class TestTripList:
    def test_empty_trip_list(self, auth_client):
        resp = auth_client.get("/trips")
        assert resp.status_code == 200

    def test_shows_trips(self, auth_client, make_trip):
        make_trip(destination="Hawaii")
        resp = auth_client.get("/trips")
        assert b"Hawaii" in resp.data

    def test_ordered_by_start_date(self, auth_client, make_trip):
        make_trip(destination="Later", start_date=date(2026, 6, 1),
                  end_date=date(2026, 6, 5))
        make_trip(destination="Earlier", start_date=date(2026, 3, 1),
                  end_date=date(2026, 3, 5))
        resp = auth_client.get("/trips")
        data = resp.data
        assert data.index(b"Earlier") < data.index(b"Later")


class TestNewTrip:
    def test_form_renders(self, auth_client):
        resp = auth_client.get("/trips/new")
        assert resp.status_code == 200

    def test_form_people_grouped_by_family(self, auth_client, make_family, make_person):
        fam = make_family(name="Groupies")
        make_person(name="Member1", family=fam)
        resp = auth_client.get("/trips/new")
        assert b"Groupies" in resp.data

    @patch("app.trips.notify_trip_created")
    def test_create_trip_success(self, mock_notify, auth_client, make_person):
        p = make_person(name="Traveler")
        data = _stop_form_data("Bali", "2026-04-01", "2026-04-10", -8.3405, 115.092)
        data["people"] = [str(p.id)]
        resp = auth_client.post("/trips/new", data=data, follow_redirects=True)
        assert b"Trip added!" in resp.data
        mock_notify.assert_called_once()

    @patch("app.trips.notify_trip_created")
    def test_create_trip_assigns_people(self, mock_notify, auth_client, make_person):
        p = make_person(name="Assigned")
        data = _stop_form_data("Fiji", "2026-05-01", "2026-05-05", -17.7134, 178.065)
        data["people"] = [str(p.id)]
        auth_client.post("/trips/new", data=data)
        from app.models import Trip
        trip = Trip.query.filter_by(destination="Fiji").first()
        assert p in trip.people

    @patch("app.trips.notify_trip_created")
    def test_create_trip_no_people(self, mock_notify, auth_client):
        data = _stop_form_data("Solo Trip", "2026-05-01", "2026-05-05", 10.0, 20.0)
        resp = auth_client.post("/trips/new", data=data, follow_redirects=True)
        assert b"Trip added!" in resp.data

    def test_create_trip_missing_lat_lng(self, auth_client):
        resp = auth_client.post("/trips/new", data={
            "stop_count": "1",
            "stop_destination_0": "Nowhere",
            "stop_latitude_0": "",
            "stop_longitude_0": "",
            "stop_start_date_0": "2026-05-01",
            "stop_end_date_0": "2026-05-05",
        }, follow_redirects=True)
        assert b"confirm the location" in resp.data

    @patch("app.trips.notify_trip_created")
    def test_create_trip_flash_message(self, mock_notify, auth_client):
        data = _stop_form_data("Flash Test", "2026-06-01", "2026-06-05", 1.0, 2.0)
        resp = auth_client.post("/trips/new", data=data, follow_redirects=True)
        assert b"Trip added!" in resp.data


class TestNewTripTitleNotes:
    @patch("app.trips.notify_trip_created")
    def test_create_trip_with_title_and_notes(self, mock_notify, auth_client):
        data = _stop_form_data("Hawaii", "2026-06-01", "2026-06-10", 21.3069, -157.8583)
        data["title"] = "Summer Vacation"
        data["notes"] = "Flight UA123"
        resp = auth_client.post("/trips/new", data=data, follow_redirects=True)
        assert b"Trip added!" in resp.data
        from app.models import Trip
        trip = Trip.query.filter_by(destination="Hawaii").first()
        assert trip.title == "Summer Vacation"
        assert trip.notes == "Flight UA123"

    @patch("app.trips.notify_trip_created")
    def test_create_trip_empty_title_stored_as_none(self, mock_notify, auth_client):
        data = _stop_form_data("Berlin", "2026-07-01", "2026-07-05", 52.52, 13.405)
        data["title"] = ""
        data["notes"] = ""
        auth_client.post("/trips/new", data=data)
        from app.models import Trip
        trip = Trip.query.filter_by(destination="Berlin").first()
        assert trip.title is None
        assert trip.notes is None

    def test_title_shown_in_trip_list(self, auth_client, make_trip):
        make_trip(destination="Rome", title="Anniversary Trip")
        resp = auth_client.get("/trips")
        assert b"Anniversary Trip" in resp.data
        assert b"Rome" in resp.data

    @freeze_time("2026-02-28")
    def test_title_shown_in_dashboard(self, auth_client, make_person, make_trip):
        p = make_person(name="Tester")
        make_trip(destination="London", title="Work Conference",
                  start_date=date(2026, 3, 10), end_date=date(2026, 3, 15), people=[p])
        resp = auth_client.get("/")
        assert b"Work Conference" in resp.data
        assert b"London" in resp.data

    def test_notes_shown_in_trip_list(self, auth_client, make_trip):
        make_trip(destination="Tokyo", notes="Hotel: Shinjuku Inn")
        resp = auth_client.get("/trips")
        assert b"Hotel: Shinjuku Inn" in resp.data


class TestEditTrip:
    @patch("app.trips.notify_trip_created")
    def test_edit_form_renders(self, mock_notify, auth_client, make_trip, make_stop):
        t = make_trip(destination="Original")
        make_stop(t, destination="Original")
        resp = auth_client.get(f"/trips/{t.id}/edit")
        assert resp.status_code == 200
        assert b"Original" in resp.data

    @patch("app.trips.notify_trip_updated")
    def test_edit_trip_success(self, mock_notify, auth_client, make_trip, make_stop):
        t = make_trip(destination="Old Name")
        make_stop(t, destination="Old Name")
        data = _stop_form_data("New Name", "2026-04-01", "2026-04-05", 10.0, 20.0)
        resp = auth_client.post(f"/trips/{t.id}/edit", data=data, follow_redirects=True)
        assert b"Trip updated!" in resp.data
        mock_notify.assert_called_once()

    @patch("app.trips.notify_trip_updated")
    def test_edit_updates_people(self, mock_notify, auth_client, make_trip, make_stop, make_person):
        p1 = make_person(name="First")
        p2 = make_person(name="Second")
        t = make_trip(destination="Crew Trip", people=[p1])
        make_stop(t, destination="Crew Trip")
        data = _stop_form_data("Crew Trip", "2026-04-01", "2026-04-05", 10.0, 20.0)
        data["people"] = [str(p2.id)]
        auth_client.post(f"/trips/{t.id}/edit", data=data)
        from app.models import Trip
        trip = Trip.query.get(t.id)
        assert p2 in trip.people
        assert p1 not in trip.people

    @patch("app.trips.notify_trip_updated")
    def test_edit_removes_all_people(self, mock_notify, auth_client, make_trip, make_stop, make_person):
        p = make_person(name="Removed")
        t = make_trip(destination="Empty Trip", people=[p])
        make_stop(t, destination="Empty Trip")
        data = _stop_form_data("Empty Trip", "2026-04-01", "2026-04-05", 10.0, 20.0)
        auth_client.post(f"/trips/{t.id}/edit", data=data)
        from app.models import Trip
        trip = Trip.query.get(t.id)
        assert trip.people == []

    @patch("app.trips.notify_trip_updated")
    def test_edit_trip_title_and_notes(self, mock_notify, auth_client, make_trip, make_stop):
        t = make_trip(destination="Paris", title="Old Title", notes="Old notes")
        make_stop(t, destination="Paris")
        data = _stop_form_data("Paris", "2026-03-01", "2026-03-05", 48.8566, 2.3522)
        data["title"] = "New Title"
        data["notes"] = "New notes"
        auth_client.post(f"/trips/{t.id}/edit", data=data)
        from app.models import Trip
        trip = Trip.query.get(t.id)
        assert trip.title == "New Title"
        assert trip.notes == "New notes"

    @patch("app.trips.notify_trip_updated")
    def test_edit_trip_clear_title_and_notes(self, mock_notify, auth_client, make_trip, make_stop):
        t = make_trip(destination="Paris", title="Has Title", notes="Has notes")
        make_stop(t, destination="Paris")
        data = _stop_form_data("Paris", "2026-03-01", "2026-03-05", 48.8566, 2.3522)
        data["title"] = ""
        data["notes"] = ""
        auth_client.post(f"/trips/{t.id}/edit", data=data)
        from app.models import Trip
        trip = Trip.query.get(t.id)
        assert trip.title is None
        assert trip.notes is None

    def test_edit_missing_lat_lng(self, auth_client, make_trip, make_stop):
        t = make_trip(destination="Bad Edit")
        make_stop(t, destination="Bad Edit")
        resp = auth_client.post(f"/trips/{t.id}/edit", data={
            "stop_count": "1",
            "stop_destination_0": "Bad Edit",
            "stop_latitude_0": "",
            "stop_longitude_0": "",
            "stop_start_date_0": "2026-04-01",
            "stop_end_date_0": "2026-04-05",
        }, follow_redirects=True)
        assert b"confirm the location" in resp.data

    def test_edit_404(self, auth_client):
        resp = auth_client.get("/trips/9999/edit")
        assert resp.status_code == 404


class TestDeleteTrip:
    @patch("app.trips.notify_trip_deleted")
    def test_delete_trip_success(self, mock_notify, auth_client, make_trip):
        t = make_trip(destination="Doomed")
        resp = auth_client.post(f"/trips/{t.id}/delete", follow_redirects=True)
        assert b"Trip deleted." in resp.data
        mock_notify.assert_called_once()

    @patch("app.trips.notify_trip_deleted")
    def test_delete_removes_trip(self, mock_notify, auth_client, make_trip):
        from app.models import Trip
        t = make_trip(destination="Gone")
        auth_client.post(f"/trips/{t.id}/delete")
        assert Trip.query.get(t.id) is None

    def test_delete_404(self, auth_client):
        resp = auth_client.post("/trips/9999/delete")
        assert resp.status_code == 404


class TestFlightData:
    @patch("app.trips.notify_trip_created")
    def test_create_trip_with_flights(self, mock_notify, auth_client, make_person):
        p = make_person(name="Flyer")
        data = _stop_form_data("London", "2026-04-01", "2026-04-10", 51.5074, -0.1278)
        data["people"] = [str(p.id)]
        data[f"outbound_flight_{p.id}"] = "BA100"
        data[f"return_flight_{p.id}"] = "BA101"
        resp = auth_client.post("/trips/new", data=data, follow_redirects=True)
        assert b"Trip added!" in resp.data
        from app.models import Trip, TripPersonFlight
        trip = Trip.query.filter_by(destination="London").first()
        fi = trip.flight_for_person(p.id)
        assert fi.outbound_flight == "BA100"
        assert fi.return_flight == "BA101"

    @patch("app.trips.notify_trip_updated")
    def test_edit_trip_updates_flights(self, mock_notify, auth_client, make_person, make_trip, make_stop, make_flight):
        p = make_person(name="Editor")
        t = make_trip(destination="Rome", people=[p])
        make_stop(t, destination="Rome")
        make_flight(t, p, outbound="AZ1")
        data = _stop_form_data("Rome", "2026-03-01", "2026-03-05", 41.9028, 12.4964)
        data["people"] = [str(p.id)]
        data[f"outbound_flight_{p.id}"] = "AZ2"
        data[f"return_flight_{p.id}"] = "AZ3"
        auth_client.post(f"/trips/{t.id}/edit", data=data)
        from app.models import Trip
        trip = Trip.query.get(t.id)
        fi = trip.flight_for_person(p.id)
        assert fi.outbound_flight == "AZ2"
        assert fi.return_flight == "AZ3"

    def test_edit_form_prepopulates_flights(self, auth_client, make_person, make_trip, make_stop, make_flight):
        p = make_person(name="Preloader")
        t = make_trip(destination="Berlin", people=[p])
        make_stop(t, destination="Berlin")
        make_flight(t, p, outbound="LH500")
        resp = auth_client.get(f"/trips/{t.id}/edit")
        assert b"LH500" in resp.data

    @freeze_time("2026-03-01")
    def test_dashboard_shows_outbound_on_start_date(self, app, make_person, make_trip, make_flight):
        from app.trips import _current_locations
        p = make_person(name="DepartDay")
        t = make_trip(destination="Tokyo", start_date=date(2026, 3, 1),
                      end_date=date(2026, 3, 5), people=[p])
        make_flight(t, p, outbound="NH100", ret="NH101")
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "DepartDay")
        assert loc["flight"] is not None
        assert loc["flight"]["number"] == "NH100"
        assert loc["flight"]["label"] == "Outbound"

    @freeze_time("2026-03-05")
    def test_dashboard_shows_return_on_end_date(self, app, make_person, make_trip, make_flight):
        from app.trips import _current_locations
        p = make_person(name="ReturnDay")
        t = make_trip(destination="Tokyo", start_date=date(2026, 3, 1),
                      end_date=date(2026, 3, 5), people=[p])
        make_flight(t, p, outbound="NH100", ret="NH101")
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "ReturnDay")
        assert loc["flight"] is not None
        assert loc["flight"]["number"] == "NH101"
        assert loc["flight"]["label"] == "Return"

    @freeze_time("2026-03-03")
    def test_dashboard_no_flight_on_middle_day(self, app, make_person, make_trip, make_flight):
        from app.trips import _current_locations
        p = make_person(name="MidTrip")
        t = make_trip(destination="Tokyo", start_date=date(2026, 3, 1),
                      end_date=date(2026, 3, 5), people=[p])
        make_flight(t, p, outbound="NH100", ret="NH101")
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "MidTrip")
        assert loc["flight"] is None

    @freeze_time("2026-03-01")
    def test_dashboard_multi_leg_outbound(self, app, make_person, make_trip, make_flight):
        from app.trips import _current_locations
        p = make_person(name="MultiOut")
        t = make_trip(destination="Tokyo", start_date=date(2026, 3, 1),
                      end_date=date(2026, 3, 5), people=[p])
        make_flight(t, p, outbound="UA100, AA200", ret="AA300")
        locs = _current_locations()
        loc = next(l for l in locs if l["name"] == "MultiOut")
        assert loc["flight"] is not None
        assert loc["flight"]["number"] == "UA100, AA200"
        assert loc["flight"]["label"] == "Outbound"
        assert "url" not in loc["flight"]

    @patch("app.trips.notify_trip_created")
    def test_create_trip_with_comma_separated_flights(self, mock_notify, auth_client, make_person):
        p = make_person(name="CommaFlyer")
        data = _stop_form_data("Tokyo", "2026-04-01", "2026-04-10", 35.6762, 139.6503)
        data["people"] = [str(p.id)]
        data[f"outbound_flight_{p.id}"] = "UA100, AA200"
        data[f"return_flight_{p.id}"] = "AA300, UA400"
        resp = auth_client.post("/trips/new", data=data, follow_redirects=True)
        assert b"Trip added!" in resp.data
        from app.models import Trip
        trip = Trip.query.filter_by(destination="Tokyo").first()
        fi = trip.flight_for_person(p.id)
        assert fi.outbound_flight == "UA100, AA200"
        assert fi.return_flight == "AA300, UA400"
