from collections import OrderedDict
from datetime import date
from unittest.mock import patch

from freezegun import freeze_time


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
        """10 AM ET (15:00 UTC in Feb/EST) → picks first trip."""
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
        """2 PM ET (19:00 UTC in Feb/EST) → picks last trip."""
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
        resp = auth_client.post("/trips/new", data={
            "destination": "Bali",
            "start_date": "2026-04-01",
            "end_date": "2026-04-10",
            "latitude": "-8.3405",
            "longitude": "115.092",
            "people": [str(p.id)],
        }, follow_redirects=True)
        assert b"Trip added!" in resp.data
        mock_notify.assert_called_once()

    @patch("app.trips.notify_trip_created")
    def test_create_trip_assigns_people(self, mock_notify, auth_client, make_person):
        p = make_person(name="Assigned")
        auth_client.post("/trips/new", data={
            "destination": "Fiji",
            "start_date": "2026-05-01",
            "end_date": "2026-05-05",
            "latitude": "-17.7134",
            "longitude": "178.065",
            "people": [str(p.id)],
        })
        from app.models import Trip
        trip = Trip.query.filter_by(destination="Fiji").first()
        assert p in trip.people

    @patch("app.trips.notify_trip_created")
    def test_create_trip_no_people(self, mock_notify, auth_client):
        resp = auth_client.post("/trips/new", data={
            "destination": "Solo Trip",
            "start_date": "2026-05-01",
            "end_date": "2026-05-05",
            "latitude": "10.0",
            "longitude": "20.0",
        }, follow_redirects=True)
        assert b"Trip added!" in resp.data

    def test_create_trip_missing_lat_lng(self, auth_client):
        resp = auth_client.post("/trips/new", data={
            "destination": "Nowhere",
            "start_date": "2026-05-01",
            "end_date": "2026-05-05",
        }, follow_redirects=True)
        assert b"Please find the destination on the map" in resp.data

    @patch("app.trips.notify_trip_created")
    def test_create_trip_flash_message(self, mock_notify, auth_client):
        resp = auth_client.post("/trips/new", data={
            "destination": "Flash Test",
            "start_date": "2026-06-01",
            "end_date": "2026-06-05",
            "latitude": "1.0",
            "longitude": "2.0",
        }, follow_redirects=True)
        assert b"Trip added!" in resp.data


class TestNewTripTitleNotes:
    @patch("app.trips.notify_trip_created")
    def test_create_trip_with_title_and_notes(self, mock_notify, auth_client):
        resp = auth_client.post("/trips/new", data={
            "destination": "Hawaii",
            "title": "Summer Vacation",
            "notes": "Flight UA123",
            "start_date": "2026-06-01",
            "end_date": "2026-06-10",
            "latitude": "21.3069",
            "longitude": "-157.8583",
        }, follow_redirects=True)
        assert b"Trip added!" in resp.data
        from app.models import Trip
        trip = Trip.query.filter_by(destination="Hawaii").first()
        assert trip.title == "Summer Vacation"
        assert trip.notes == "Flight UA123"

    @patch("app.trips.notify_trip_created")
    def test_create_trip_empty_title_stored_as_none(self, mock_notify, auth_client):
        auth_client.post("/trips/new", data={
            "destination": "Berlin",
            "title": "",
            "notes": "",
            "start_date": "2026-07-01",
            "end_date": "2026-07-05",
            "latitude": "52.52",
            "longitude": "13.405",
        })
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
    def test_edit_form_renders(self, mock_notify, auth_client, make_trip):
        t = make_trip(destination="Original")
        resp = auth_client.get(f"/trips/{t.id}/edit")
        assert resp.status_code == 200
        assert b"Original" in resp.data

    @patch("app.trips.notify_trip_updated")
    def test_edit_trip_success(self, mock_notify, auth_client, make_trip):
        t = make_trip(destination="Old Name")
        resp = auth_client.post(f"/trips/{t.id}/edit", data={
            "destination": "New Name",
            "start_date": "2026-04-01",
            "end_date": "2026-04-05",
            "latitude": "10.0",
            "longitude": "20.0",
        }, follow_redirects=True)
        assert b"Trip updated!" in resp.data
        mock_notify.assert_called_once()

    @patch("app.trips.notify_trip_updated")
    def test_edit_updates_people(self, mock_notify, auth_client, make_trip, make_person):
        p1 = make_person(name="First")
        p2 = make_person(name="Second")
        t = make_trip(destination="Crew Trip", people=[p1])
        auth_client.post(f"/trips/{t.id}/edit", data={
            "destination": "Crew Trip",
            "start_date": "2026-04-01",
            "end_date": "2026-04-05",
            "latitude": "10.0",
            "longitude": "20.0",
            "people": [str(p2.id)],
        })
        from app.models import Trip
        trip = Trip.query.get(t.id)
        assert p2 in trip.people
        assert p1 not in trip.people

    @patch("app.trips.notify_trip_updated")
    def test_edit_removes_all_people(self, mock_notify, auth_client, make_trip, make_person):
        p = make_person(name="Removed")
        t = make_trip(destination="Empty Trip", people=[p])
        auth_client.post(f"/trips/{t.id}/edit", data={
            "destination": "Empty Trip",
            "start_date": "2026-04-01",
            "end_date": "2026-04-05",
            "latitude": "10.0",
            "longitude": "20.0",
        })
        from app.models import Trip
        trip = Trip.query.get(t.id)
        assert trip.people == []

    @patch("app.trips.notify_trip_updated")
    def test_edit_trip_title_and_notes(self, mock_notify, auth_client, make_trip):
        t = make_trip(destination="Paris", title="Old Title", notes="Old notes")
        auth_client.post(f"/trips/{t.id}/edit", data={
            "destination": "Paris",
            "title": "New Title",
            "notes": "New notes",
            "start_date": "2026-03-01",
            "end_date": "2026-03-05",
            "latitude": "48.8566",
            "longitude": "2.3522",
        })
        from app.models import Trip
        trip = Trip.query.get(t.id)
        assert trip.title == "New Title"
        assert trip.notes == "New notes"

    @patch("app.trips.notify_trip_updated")
    def test_edit_trip_clear_title_and_notes(self, mock_notify, auth_client, make_trip):
        t = make_trip(destination="Paris", title="Has Title", notes="Has notes")
        auth_client.post(f"/trips/{t.id}/edit", data={
            "destination": "Paris",
            "title": "",
            "notes": "",
            "start_date": "2026-03-01",
            "end_date": "2026-03-05",
            "latitude": "48.8566",
            "longitude": "2.3522",
        })
        from app.models import Trip
        trip = Trip.query.get(t.id)
        assert trip.title is None
        assert trip.notes is None

    def test_edit_missing_lat_lng(self, auth_client, make_trip):
        t = make_trip(destination="Bad Edit")
        resp = auth_client.post(f"/trips/{t.id}/edit", data={
            "destination": "Bad Edit",
            "start_date": "2026-04-01",
            "end_date": "2026-04-05",
        }, follow_redirects=True)
        assert b"Please find the destination on the map" in resp.data

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
        resp = auth_client.post("/trips/new", data={
            "destination": "London",
            "start_date": "2026-04-01",
            "end_date": "2026-04-10",
            "latitude": "51.5074",
            "longitude": "-0.1278",
            "people": [str(p.id)],
            f"outbound_flight_{p.id}": "BA100",
            f"return_flight_{p.id}": "BA101",
        }, follow_redirects=True)
        assert b"Trip added!" in resp.data
        from app.models import Trip, TripPersonFlight
        trip = Trip.query.filter_by(destination="London").first()
        fi = trip.flight_for_person(p.id)
        assert fi.outbound_flight == "BA100"
        assert fi.return_flight == "BA101"

    @patch("app.trips.notify_trip_updated")
    def test_edit_trip_updates_flights(self, mock_notify, auth_client, make_person, make_trip, make_flight):
        p = make_person(name="Editor")
        t = make_trip(destination="Rome", people=[p])
        make_flight(t, p, outbound="AZ1")
        auth_client.post(f"/trips/{t.id}/edit", data={
            "destination": "Rome",
            "start_date": "2026-03-01",
            "end_date": "2026-03-05",
            "latitude": "41.9028",
            "longitude": "12.4964",
            "people": [str(p.id)],
            f"outbound_flight_{p.id}": "AZ2",
            f"return_flight_{p.id}": "AZ3",
        })
        from app.models import Trip
        trip = Trip.query.get(t.id)
        fi = trip.flight_for_person(p.id)
        assert fi.outbound_flight == "AZ2"
        assert fi.return_flight == "AZ3"

    def test_edit_form_prepopulates_flights(self, auth_client, make_person, make_trip, make_flight):
        p = make_person(name="Preloader")
        t = make_trip(destination="Berlin", people=[p])
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
        resp = auth_client.post("/trips/new", data={
            "destination": "Tokyo",
            "start_date": "2026-04-01",
            "end_date": "2026-04-10",
            "latitude": "35.6762",
            "longitude": "139.6503",
            "people": [str(p.id)],
            f"outbound_flight_{p.id}": "UA100, AA200",
            f"return_flight_{p.id}": "AA300, UA400",
        }, follow_redirects=True)
        assert b"Trip added!" in resp.data
        from app.models import Trip
        trip = Trip.query.filter_by(destination="Tokyo").first()
        fi = trip.flight_for_person(p.id)
        assert fi.outbound_flight == "UA100, AA200"
        assert fi.return_flight == "AA300, UA400"
