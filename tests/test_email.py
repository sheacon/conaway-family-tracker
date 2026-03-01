from datetime import date
from unittest.mock import patch

from app import db
from app.models import Config, Trip
from app.email import (
    _get_recipients, _send_email, _format_people, _format_dates,
    _subject, _trip_html, notifications_paused,
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
    def test_sends_via_resend(self, mock_send, app, make_person):
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
    def test_date_range(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
        result = _format_dates(t)
        assert "Mar 1, 2026" in result
        assert "Mar 5, 2026" in result
        assert "–" in result

    def test_same_date(self, app, make_trip):
        t = make_trip(start_date=date(2026, 3, 1), end_date=date(2026, 3, 1))
        assert _format_dates(t) == "Mar 1, 2026"


class TestSubject:
    def test_format(self, app, make_person, make_trip):
        p = make_person(name="Alice")
        t = make_trip(destination="Paris", start_date=date(2026, 3, 1),
                      end_date=date(2026, 3, 5), people=[p])
        result = _subject("New Trip", t)
        assert result.startswith("New Trip:")
        assert "Alice" in result
        assert "Paris" in result

    def test_uses_display_name_with_title(self, app, make_person, make_trip):
        p = make_person(name="Alice")
        t = make_trip(destination="Paris", title="Spring Break",
                      start_date=date(2026, 3, 1), end_date=date(2026, 3, 5), people=[p])
        result = _subject("New Trip", t)
        assert "Spring Break" in result
        assert "Paris" not in result


class TestTripHtml:
    def test_contains_destination_and_people(self, app, make_person, make_trip):
        p = make_person(name="Bob")
        t = make_trip(destination="Rome", people=[p])
        html = _trip_html("Test Heading", t)
        assert "Rome" in html
        assert "Bob" in html
        assert "Test Heading" in html
        assert "conaway-family-tracker.fly.dev" in html

    def test_includes_title_when_set(self, app, make_person, make_trip):
        p = make_person(name="Carol")
        t = make_trip(destination="Rome", title="Italy Getaway", people=[p])
        html = _trip_html("Heading", t)
        assert "Italy Getaway" in html

    def test_excludes_title_when_not_set(self, app, make_person, make_trip):
        p = make_person(name="Dan")
        t = make_trip(destination="Rome", people=[p])
        html = _trip_html("Heading", t)
        assert "<strong>Trip:</strong>" not in html

    def test_includes_notes_when_set(self, app, make_person, make_trip):
        p = make_person(name="Eve")
        t = make_trip(destination="Rome", notes="Hotel: Grand", people=[p])
        html = _trip_html("Heading", t)
        assert "Hotel: Grand" in html

    def test_excludes_notes_when_not_set(self, app, make_person, make_trip):
        p = make_person(name="Frank")
        t = make_trip(destination="Rome", people=[p])
        html = _trip_html("Heading", t)
        assert "<strong>Notes:</strong>" not in html

    def test_includes_flights(self, app, make_person, make_trip):
        p = make_person(name="Gina")
        t = make_trip(destination="Tokyo", people=[p],
                      outbound_flight="NH100", return_flight="NH101")
        html = _trip_html("Heading", t)
        assert "<strong>Flights:</strong>" in html
        assert "NH100" in html
        assert "NH101" in html

    def test_outbound_only(self, app, make_person, make_trip):
        p = make_person(name="Person G")
        t = make_trip(destination="Berlin", people=[p], outbound_flight="LH400")
        html = _trip_html("Heading", t)
        assert "LH400" in html
        assert "Outbound" in html

    def test_return_only(self, app, make_person, make_trip):
        p = make_person(name="Iris")
        t = make_trip(destination="Madrid", people=[p], return_flight="IB500")
        html = _trip_html("Heading", t)
        assert "IB500" in html
        assert "Return" in html

    def test_excludes_flights_when_not_set(self, app, make_person, make_trip):
        p = make_person(name="Jack")
        t = make_trip(destination="Rome", people=[p])
        html = _trip_html("Heading", t)
        assert "<strong>Flights:</strong>" not in html

    def test_multi_leg_flights(self, app, make_person, make_trip):
        p = make_person(name="MultiLeg")
        t = make_trip(destination="Tokyo", people=[p],
                      outbound_flight="UA100, AA200", return_flight="AA300, UA400")
        html = _trip_html("Heading", t)
        assert "flightaware.com/live/flight/UAL100" in html
        assert "flightaware.com/live/flight/AAL200" in html


class TestNotifyFunctions:
    @patch("app.email._send_email")
    def test_created(self, mock_send, app, make_person, make_trip):
        t = make_trip(destination="Nara", people=[make_person(name="Nora")])
        notify_trip_created(t)
        mock_send.assert_called_once()
        assert "New Trip" in mock_send.call_args[0][0]

    @patch("app.email._send_email")
    def test_updated(self, mock_send, app, make_person, make_trip):
        t = make_trip(destination="Uji", people=[make_person(name="Uma")])
        notify_trip_updated(t)
        mock_send.assert_called_once()
        assert "Trip Updated" in mock_send.call_args[0][0]

    @patch("app.email._send_email")
    def test_deleted(self, mock_send, app, make_person, make_trip):
        t = make_trip(destination="Delhi", people=[make_person(name="Del")])
        notify_trip_deleted(t)
        mock_send.assert_called_once()
        assert "Trip Cancelled" in mock_send.call_args[0][0]

    @patch("app.email._send_email")
    def test_starting_soon(self, mock_send, app, make_person, make_trip):
        t = make_trip(destination="Seoul", people=[make_person(name="Soon")])
        notify_trip_starting_soon(t)
        mock_send.assert_called_once()
        assert "Trip in 3 Days" in mock_send.call_args[0][0]

    @patch("app.email._send_email")
    def test_started(self, mock_send, app, make_person, make_trip):
        t = make_trip(destination="Stockholm", people=[make_person(name="Start")])
        notify_trip_started(t)
        mock_send.assert_called_once()
        assert "Trip Starting Today" in mock_send.call_args[0][0]

    @patch("app.email._send_email")
    def test_ended(self, mock_send, app, make_person, make_trip):
        t = make_trip(destination="Edinburgh", people=[make_person(name="End")])
        notify_trip_ended(t)
        mock_send.assert_called_once()
        assert "Trip Ended" in mock_send.call_args[0][0]


class TestNotificationsPaused:
    def test_false_when_no_config(self, app):
        assert notifications_paused() is False

    def test_false_when_zero(self, app):
        db.session.add(Config(key="notifications_paused", value="0"))
        db.session.commit()
        assert notifications_paused() is False

    def test_true_when_one(self, app):
        db.session.add(Config(key="notifications_paused", value="1"))
        db.session.commit()
        assert notifications_paused() is True


class TestCrudNotifiersSkipWhenPaused:
    def _pause(self):
        db.session.add(Config(key="notifications_paused", value="1"))
        db.session.commit()

    @patch("app.email._send_email")
    def test_created_skipped(self, mock_send, app, make_person, make_trip):
        self._pause()
        notify_trip_created(make_trip(people=[make_person(name="P1")]))
        mock_send.assert_not_called()

    @patch("app.email._send_email")
    def test_updated_skipped(self, mock_send, app, make_person, make_trip):
        self._pause()
        notify_trip_updated(make_trip(people=[make_person(name="P2")]))
        mock_send.assert_not_called()

    @patch("app.email._send_email")
    def test_deleted_skipped(self, mock_send, app, make_person, make_trip):
        self._pause()
        notify_trip_deleted(make_trip(people=[make_person(name="P3")]))
        mock_send.assert_not_called()


class TestScheduledNotifiersSendWhenPaused:
    def _pause(self):
        db.session.add(Config(key="notifications_paused", value="1"))
        db.session.commit()

    @patch("app.email._send_email")
    def test_starting_soon_still_sends(self, mock_send, app, make_person, make_trip):
        self._pause()
        notify_trip_starting_soon(make_trip(people=[make_person(name="S1")]))
        mock_send.assert_called_once()

    @patch("app.email._send_email")
    def test_started_still_sends(self, mock_send, app, make_person, make_trip):
        self._pause()
        notify_trip_started(make_trip(people=[make_person(name="S2")]))
        mock_send.assert_called_once()

    @patch("app.email._send_email")
    def test_ended_still_sends(self, mock_send, app, make_person, make_trip):
        self._pause()
        notify_trip_ended(make_trip(people=[make_person(name="S3")]))
        mock_send.assert_called_once()
