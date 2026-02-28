import logging

import resend
from flask import current_app

from app.models import Person

logger = logging.getLogger(__name__)


def _get_recipients():
    return [p.email for p in Person.query.filter(Person.email.isnot(None)).all()]


def _send_email(subject, html_body):
    api_key = current_app.config.get("RESEND_API_KEY")
    if not api_key:
        return
    recipients = _get_recipients()
    if not recipients:
        return
    resend.api_key = api_key
    try:
        resend.Emails.send({
            "from": current_app.config["RESEND_FROM_EMAIL"],
            "to": recipients,
            "subject": subject,
            "html": html_body,
        })
    except Exception:
        logger.exception("Failed to send email: %s", subject)


def _format_people(trip):
    return ", ".join(p.name for p in trip.people) or "No one assigned"


def _format_dates(trip):
    fmt = "%b %-d, %Y"
    if trip.start_date == trip.end_date:
        return trip.start_date.strftime(fmt)
    return f"{trip.start_date.strftime(fmt)} – {trip.end_date.strftime(fmt)}"


def _subject(prefix, trip):
    people = _format_people(trip)
    dates = _format_dates(trip)
    return f"{prefix}: {people} – {trip.destination} ({dates})"


def _trip_html(heading, trip):
    return (
        f"<h2>{heading}</h2>"
        f"<p><strong>Destination:</strong> {trip.destination}</p>"
        f"<p><strong>Who:</strong> {_format_people(trip)}</p>"
        f"<p><strong>When:</strong> {_format_dates(trip)}</p>"
        f'<p><a href="https://conaway-family-tracker.fly.dev/">View Tracker</a></p>'
    )


def notify_trip_created(trip):
    _send_email(
        _subject("New trip", trip),
        _trip_html("New Trip Added", trip),
    )


def notify_trip_updated(trip):
    _send_email(
        _subject("Trip updated", trip),
        _trip_html("Trip Updated", trip),
    )


def notify_trip_deleted(trip):
    _send_email(
        _subject("Trip cancelled", trip),
        _trip_html("Trip Cancelled", trip),
    )


def notify_trip_starting_soon(trip):
    _send_email(
        _subject("Trip in 3 days", trip),
        _trip_html("Trip Starting Soon", trip),
    )


def notify_trip_started(trip):
    _send_email(
        _subject("Trip starting today", trip),
        _trip_html("Trip Starting Today", trip),
    )


def notify_trip_ended(trip):
    _send_email(
        _subject("Trip ended", trip),
        _trip_html("Trip Ended", trip),
    )
