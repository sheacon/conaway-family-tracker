from datetime import date
from unittest.mock import patch, MagicMock

from app.models import Trip, Person
from app import db
from app.email import (
    _get_recipients, _send_email, _format_people, _format_dates,
    _subject, _trip_html,
    notify_trip_created, notify_trip_updated, notify_trip_deleted,
    notify_trip_starting_soon, notify_trip_started, notify_trip_ended,
)


class TestGetRecipients:
    def test_returns_emails(self, app, make_person):
        make_person(name="A", email="a@example.com")
        make_person(name="B", email="b@example.com")
        assert set(_get_recipients()) == {"a@example.com", "b@example.com"}

    def test_skips_none_emails(self, app, make_person):
        make_person(name="C", email="c@example.com")
        make_person(name="D", email=None)
        assert _get_recipients() == ["c@example.com"]

    def test_empty_when_no_emails(self, app, make_person):
        make_person(name="E", email=None)
        assert _get_recipients() == []


class TestSendEmail:
    @patch("app.email.resend.Emails.send")
    def test_noop_without_api_key(self, mock_send, app, make_person):
        make_person(name="F", email="f@example.com")
        app.config["RESEND_API_KEY"] = None
        _send_email("test", "<p>test</p>")
        mock_send.assert_not_called()

    @patch("app.email.resend.Emails.send")
    def test_noop_without_recipients(self, mock_send, app):
        _send_email("test", "<p>test</p>")
        mock_send.assert_not_called()

    @patch("app.email.resend.Emails.send")
    def test_success_calls_resend(self, mock_send, app, make_person):
        make_person(name="G", email="g@example.com")
        _send_email("Test Subject", "<p>body</p>")
        mock_send.assert_called_once_with({
            "from": "test@example.com",
            "to": ["g@example.com"],
            "subject": "Test Subject",
            "html": "<p>body</p>",
        })

    @patch("app.email.resend.Emails.send", side_effect=Exception("API error"))
    def test_exception_swallowed(self, mock_send, app, make_person):
        make_person(name="H", email="h@example.com")
        _send_email("Fail", "<p>fail</p>")  # should not raise


class TestFormatPeople:
    def test_multiple_people(self, app, make_person, make_trip):
        p1 = make_person(name="Alice")
        p2 = make_person(name="Bob")
        t = make_trip(people=[p1, p2])
        result = _format_people(t)
        assert "Alice" in result
        assert "Bob" in result

    def test_single_person(self, app, make_person, make_trip):
        p = make_person(name="Solo")
        t = make_trip(people=[p])
        assert _format_people(t) == "Solo"

    def test_no_people(self, app, make_trip):
        t = make_trip()
        assert _format_people(t) == "No one assigned"


class TestFormatDates:
    def test_different_dates(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        result = _format_dates(t)
        assert "Mar 1, 2026" in result
        assert "Mar 5, 2026" in result
        assert "–" in result

    def test_same_date(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 1))
        assert _format_dates(t) == "Mar 1, 2026"


class TestSubject:
    def test_subject_format(self, app, make_person, make_trip):
        p = make_person(name="Alice")
        t = make_trip(destination="Paris", start_date=date(2026, 3, 1),
                      end_date=date(2026, 3, 5), people=[p])
        result = _subject("New Trip", t)
        assert result.startswith("New Trip:")
        assert "Alice" in result
        assert "Paris" in result


class TestTripHtml:
    def test_contains_destination(self, app, make_person, make_trip):
        p = make_person(name="Bob")
        t = make_trip(destination="Rome", people=[p])
        html = _trip_html("Test Heading", t)
        assert "Rome" in html
        assert "Bob" in html
        assert "Test Heading" in html
        assert "conaway-family-tracker.fly.dev" in html


class TestNotifyFunctions:
    @patch("app.email._send_email")
    def test_notify_trip_created(self, mock_send, app, make_person, make_trip):
        p = make_person(name="Nora")
        t = make_trip(destination="Nara", people=[p])
        notify_trip_created(t)
        mock_send.assert_called_once()
        subject = mock_send.call_args[0][0]
        html = mock_send.call_args[0][1]
        assert "New Trip" in subject
        assert "New Trip Added" in html

    @patch("app.email._send_email")
    def test_notify_trip_updated(self, mock_send, app, make_person, make_trip):
        p = make_person(name="Uma")
        t = make_trip(destination="Uji", people=[p])
        notify_trip_updated(t)
        mock_send.assert_called_once()
        assert "Trip Updated" in mock_send.call_args[0][0]

    @patch("app.email._send_email")
    def test_notify_trip_deleted(self, mock_send, app, make_person, make_trip):
        p = make_person(name="Del")
        t = make_trip(destination="Delhi", people=[p])
        notify_trip_deleted(t)
        mock_send.assert_called_once()
        assert "Trip Cancelled" in mock_send.call_args[0][0]

    @patch("app.email._send_email")
    def test_notify_trip_starting_soon(self, mock_send, app, make_person, make_trip):
        p = make_person(name="Soon")
        t = make_trip(destination="Seoul", people=[p])
        notify_trip_starting_soon(t)
        mock_send.assert_called_once()
        assert "Trip in 3 Days" in mock_send.call_args[0][0]

    @patch("app.email._send_email")
    def test_notify_trip_started(self, mock_send, app, make_person, make_trip):
        p = make_person(name="Start")
        t = make_trip(destination="Stockholm", people=[p])
        notify_trip_started(t)
        mock_send.assert_called_once()
        assert "Trip Starting Today" in mock_send.call_args[0][0]

    @patch("app.email._send_email")
    def test_notify_trip_ended(self, mock_send, app, make_person, make_trip):
        p = make_person(name="End")
        t = make_trip(destination="Edinburgh", people=[p])
        notify_trip_ended(t)
        mock_send.assert_called_once()
        assert "Trip Ended" in mock_send.call_args[0][0]
