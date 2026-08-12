"""Tests for email notification module."""

from datetime import date
from unittest.mock import patch, MagicMock

from freezegun import freeze_time

from app import db
from app.models import Config


class TestGetRecipients:
    def test_returns_people_with_email(self, app, make_person):
        make_person(name="A", email="a@example.com")
        make_person(name="B", email="b@example.com")
        make_person(name="NoEmail")
        from app.email import _get_recipients
        recipients = _get_recipients()
        assert set(recipients) == {"a@example.com", "b@example.com"}

    def test_filters_by_notification_type(self, app, make_person):
        p1 = make_person(name="A", email="a@example.com")
        p2 = make_person(name="B", email="b@example.com")
        p1.set_enabled_notifications(["trip_created"])
        p2.set_enabled_notifications(["trip_started"])
        db.session.commit()
        from app.email import _get_recipients
        recipients = _get_recipients(notification_type="trip_created")
        assert recipients == ["a@example.com"]

    def test_no_type_returns_all_with_email(self, app, make_person):
        make_person(name="A", email="a@example.com")
        from app.email import _get_recipients
        recipients = _get_recipients(notification_type=None)
        assert "a@example.com" in recipients


class TestSendEmailTo:
    def test_sends_via_resend(self, app, make_person):
        from app.email import _send_email_to
        with patch("app.email.resend.Emails.send") as mock_send:
            _send_email_to(["a@b.com"], "Subject", "<p>Body</p>")
        mock_send.assert_called_once()
        payload = mock_send.call_args[0][0]
        assert payload["to"] == ["a@b.com"]
        assert payload["subject"] == "Subject"
        assert payload["html"] == "<p>Body</p>"

    def test_skips_when_no_api_key(self, app):
        app.config["RESEND_API_KEY"] = None
        from app.email import _send_email_to
        with patch("app.email.resend.Emails.send") as mock_send:
            _send_email_to(["a@b.com"], "Subject", "<p>Body</p>")
        mock_send.assert_not_called()

    def test_skips_empty_recipients(self, app):
        from app.email import _send_email_to
        with patch("app.email.resend.Emails.send") as mock_send:
            _send_email_to([], "Subject", "<p>Body</p>")
        mock_send.assert_not_called()

    def test_handles_send_exception(self, app):
        from app.email import _send_email_to
        with patch("app.email.resend.Emails.send", side_effect=Exception("API error")):
            # Should not raise
            _send_email_to(["a@b.com"], "Subject", "<p>Body</p>")

    def test_includes_attachments(self, app):
        from app.email import _send_email_to
        attachment = {"filename": "test.png", "content": "base64data"}
        with patch("app.email.resend.Emails.send") as mock_send:
            _send_email_to(["a@b.com"], "Subject", "<p>Body</p>",
                          attachments=[attachment])
        payload = mock_send.call_args[0][0]
        assert payload["attachments"] == [attachment]


class TestFormatHelpers:
    def test_format_people(self, app, make_person, make_trip):
        from app.email import _format_people
        p1 = make_person(name="Alice")
        p2 = make_person(name="Bob")
        t = make_trip(people=[p1, p2])
        assert "Alice" in _format_people(t)
        assert "Bob" in _format_people(t)

    def test_format_people_no_one(self, app, make_trip):
        from app.email import _format_people
        t = make_trip()
        assert _format_people(t) == "No one assigned"

    @freeze_time("2026-06-01", tz_offset=0)
    def test_subject(self, app, make_person, make_trip):
        from app.email import _subject
        p = make_person(name="Alice")
        t = make_trip(destination="Paris", start_date=date(2026, 6, 1),
                      end_date=date(2026, 6, 5), people=[p])
        subj = _subject("New Trip", t)
        assert "New Trip" in subj
        assert "Alice" in subj
        assert "Paris" in subj

    @freeze_time("2026-06-01", tz_offset=0)
    def test_subject_uses_display_name(self, app, make_person, make_trip):
        from app.email import _subject
        p = make_person(name="Alice")
        t = make_trip(destination="Paris", title="Spring Break",
                      start_date=date(2026, 6, 1), end_date=date(2026, 6, 5),
                      people=[p])
        subj = _subject("New Trip", t)
        assert "Spring Break" in subj


class TestTripHtml:
    @freeze_time("2026-06-01", tz_offset=0)
    def test_basic_trip(self, app, make_person, make_trip):
        from app.email import _trip_html
        p = make_person(name="Alice")
        t = make_trip(destination="Paris", people=[p])
        html = _trip_html("Test Heading", t)
        assert "Test Heading" in html
        assert "Paris" in html
        assert "Alice" in html

    @freeze_time("2026-06-01", tz_offset=0)
    def test_with_title(self, app, make_trip):
        from app.email import _trip_html
        t = make_trip(title="Spring Break", destination="Paris")
        html = _trip_html("Heading", t)
        assert "Spring Break" in html

    @freeze_time("2026-06-01", tz_offset=0)
    def test_with_notes(self, app, make_trip):
        from app.email import _trip_html
        t = make_trip(notes="Pack sunscreen")
        html = _trip_html("Heading", t)
        assert "Pack sunscreen" in html

    @freeze_time("2026-06-01", tz_offset=0)
    def test_with_flights(self, app, make_trip):
        from app.email import _trip_html
        t = make_trip(outbound_flight="AA100", return_flight="DL200")
        html = _trip_html("Heading", t)
        assert "AA100" in html
        assert "DL200" in html
        assert "flightaware.com" in html

    @freeze_time("2026-06-01", tz_offset=0)
    def test_multi_stop(self, app, make_trip, make_stop):
        from app.email import _trip_html
        t = make_trip(start_date=date(2026, 6, 1), end_date=date(2026, 6, 10))
        make_stop(t, order=0, destination="Nashville",
                  start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        make_stop(t, order=1, destination="Memphis",
                  start_date=date(2026, 6, 6), end_date=date(2026, 6, 10))
        html = _trip_html("Heading", t)
        assert "Nashville" in html
        assert "Memphis" in html
        assert "Route" in html


class TestDashboardHtml:
    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_includes_action_links(self, app):
        from app.email import _dashboard_html
        html = _dashboard_html()
        assert "/trips/new" in html
        assert "/trips" in html

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_includes_upcoming_trips(self, app, make_trip, make_person):
        from app.email import _dashboard_html
        p = make_person(name="Alice")
        make_trip(destination="Tokyo", start_date=date(2026, 6, 10),
                  end_date=date(2026, 6, 15), people=[p])
        html = _dashboard_html()
        assert "Tokyo" in html
        assert "Alice" in html

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_includes_current_locations(self, app, make_person):
        from app.email import _dashboard_html
        make_person(name="Bob", location_label="Chicago")
        html = _dashboard_html()
        assert "Bob" in html
        assert "Chicago" in html


class TestMapImageUrl:
    def test_returns_none_when_no_image(self, app, tmp_path):
        from app.email import _map_image_url
        with patch("app.map_generator._cache_paths",
                   return_value=(tmp_path / "missing.png", tmp_path / "h")):
            assert _map_image_url() is None

    def test_returns_url_with_token_and_version(self, app, tmp_path):
        from app.email import BASE_URL, _map_image_url
        from app.map_generator import map_token
        img = tmp_path / "map.png"
        img.write_bytes(b"\x89PNG fake")
        hash_file = tmp_path / "map.hash"
        hash_file.write_text("abc123\n")
        with patch("app.map_generator._cache_paths",
                   return_value=(img, hash_file)):
            url = _map_image_url()
            assert url == f"{BASE_URL}/map/{map_token()}.jpg?v=abc123"

    def test_version_falls_back_to_content_hash(self, app, tmp_path):
        """Caches written before map_cache.hash existed still get a version."""
        from app.email import _map_image_url
        img = tmp_path / "map.png"
        img.write_bytes(b"\x89PNG fake")
        with patch("app.map_generator._cache_paths",
                   return_value=(img, tmp_path / "missing.hash")):
            url = _map_image_url()
        assert url is not None
        assert "?v=" in url
        assert not url.endswith("?v=")

    def test_dashboard_html_uses_url_not_cid(self, app, tmp_path):
        from app.email import _dashboard_html
        img = tmp_path / "map.png"
        img.write_bytes(b"\x89PNG fake")
        hash_file = tmp_path / "map.hash"
        hash_file.write_text("abc123")
        with patch("app.map_generator._cache_paths",
                   return_value=(img, hash_file)):
            html = _dashboard_html()
        assert "cid:" not in html
        assert "/map/" in html
        assert ".jpg?v=abc123" in html


class TestNotifyFunctions:
    """Test that CRUD notifications respect pause and scheduled ones don't."""

    def _pause_notifications(self):
        db.session.add(Config(key="notifications_paused", value="1"))
        db.session.commit()

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_created_respects_pause(self, app, make_trip, make_person):
        from app.email import notify_trip_created
        make_person(name="A", email="a@example.com")
        self._pause_notifications()
        t = make_trip()
        with patch("app.email._notify") as mock:
            notify_trip_created(t)
        mock.assert_not_called()

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_updated_respects_pause(self, app, make_trip, make_person):
        from app.email import notify_trip_updated
        make_person(name="A", email="a@example.com")
        self._pause_notifications()
        t = make_trip()
        with patch("app.email._notify") as mock:
            notify_trip_updated(t)
        mock.assert_not_called()

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_deleted_respects_pause(self, app, make_trip, make_person):
        from app.email import notify_trip_deleted
        make_person(name="A", email="a@example.com")
        self._pause_notifications()
        t = make_trip()
        with patch("app.email._notify") as mock:
            notify_trip_deleted(t)
        mock.assert_not_called()

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_starting_soon_ignores_pause(self, app, make_trip, make_person):
        from app.email import notify_trip_starting_soon
        make_person(name="A", email="a@example.com")
        self._pause_notifications()
        t = make_trip()
        with patch("app.email._notify") as mock:
            notify_trip_starting_soon(t)
        mock.assert_called_once()

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_started_ignores_pause(self, app, make_trip, make_person):
        from app.email import notify_trip_started
        make_person(name="A", email="a@example.com")
        self._pause_notifications()
        t = make_trip()
        with patch("app.email._notify") as mock:
            notify_trip_started(t)
        mock.assert_called_once()

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_ended_ignores_pause(self, app, make_trip, make_person):
        from app.email import notify_trip_ended
        make_person(name="A", email="a@example.com")
        self._pause_notifications()
        t = make_trip()
        with patch("app.email._notify") as mock:
            notify_trip_ended(t)
        mock.assert_called_once()

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_created_sends_when_not_paused(self, app, make_trip, make_person):
        from app.email import notify_trip_created
        make_person(name="A", email="a@example.com")
        t = make_trip()
        with patch("app.email._notify") as mock:
            notify_trip_created(t)
        mock.assert_called_once()

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_notify_passes_notification_type(self, app, make_trip, make_person):
        from app.email import notify_trip_created
        make_person(name="A", email="a@example.com")
        t = make_trip()
        with patch("app.email._notify") as mock:
            notify_trip_created(t)
        call_kwargs = mock.call_args
        assert call_kwargs[1]["notification_type"] == "trip_created" or \
            "trip_created" in str(call_kwargs)


class TestSendTestNotification:
    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_success(self, app):
        from app.email import send_test_notification
        with patch("app.email._send_email_to") as mock:
            result = send_test_notification("test@example.com")
        assert result is True
        mock.assert_called_once()
        args = mock.call_args[0]
        assert args[0] == ["test@example.com"]
        assert "Test Notification" in args[1]

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_failure_returns_false(self, app):
        from app.email import send_test_notification
        with patch("app.email._send_email_to", side_effect=Exception("fail")):
            result = send_test_notification("test@example.com")
        assert result is False
