import logging

import resend
from flask import current_app

from app import db
from app.models import Config, Person, TripPersonFlight

logger = logging.getLogger(__name__)


def notifications_paused() -> bool:
    """Return True if CRUD trip notifications are paused via admin toggle."""
    row = db.session.get(Config, "notifications_paused")
    return row is not None and row.value == "1"


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
    return f"{prefix}: {people} – {trip.display_name} ({dates})"


def _trip_html(heading, trip):
    html = f"<h2>{heading}</h2>"
    if trip.title:
        html += f"<p><strong>Trip:</strong> {trip.title}</p>"
    if trip.is_multi_stop:
        html += f"<p><strong>Route:</strong> {trip.destinations_summary}</p>"
        html += "<ol>"
        for stop in trip.stops:
            fmt = "%b %-d"
            html += f"<li>{stop.destination}: {stop.start_date.strftime(fmt)} – {stop.end_date.strftime(fmt)}</li>"
        html += "</ol>"
    else:
        html += f"<p><strong>Destination:</strong> {trip.destination}</p>"
    html += f"<p><strong>Who:</strong> {_format_people(trip)}</p>"
    html += f"<p><strong>When:</strong> {_format_dates(trip)}</p>"
    if trip.notes:
        html += f"<p><strong>Notes:</strong> {trip.notes}</p>"
    if trip.flight_info:
        html += "<p><strong>Flights:</strong></p><ul>"
        from collections import OrderedDict
        flight_groups = OrderedDict()
        for fi in trip.flight_info:
            key = (fi.outbound_flight or "", fi.return_flight or "")
            flight_groups.setdefault(key, []).append(fi.person.name)
        for (outbound, ret), names in flight_groups.items():
            parts = []
            if outbound:
                links = ", ".join(
                    f'<a href="{TripPersonFlight.flight_url(n.strip())}">{n.strip()}</a>'
                    for n in outbound.split(",") if n.strip()
                )
                parts.append(f"Outbound: {links}")
            if ret:
                links = ", ".join(
                    f'<a href="{TripPersonFlight.flight_url(n.strip())}">{n.strip()}</a>'
                    for n in ret.split(",") if n.strip()
                )
                parts.append(f"Return: {links}")
            html += f"<li>{', '.join(names)}: {' / '.join(parts)}</li>"
        html += "</ul>"
    html += '<p><a href="https://conaway-family-tracker.fly.dev/">View Tracker</a></p>'
    return html


def notify_trip_created(trip):
    if notifications_paused():
        return
    _send_email(
        _subject("New Trip", trip),
        _trip_html("New Trip Added", trip),
    )


def notify_trip_updated(trip):
    if notifications_paused():
        return
    _send_email(
        _subject("Trip Updated", trip),
        _trip_html("Trip Updated", trip),
    )


def notify_trip_deleted(trip):
    if notifications_paused():
        return
    _send_email(
        _subject("Trip Cancelled", trip),
        _trip_html("Trip Cancelled", trip),
    )


def notify_trip_starting_soon(trip):
    _send_email(
        _subject("Trip in 3 Days", trip),
        _trip_html("Trip Starting Soon", trip),
    )


def notify_trip_started(trip):
    _send_email(
        _subject("Trip Starting Today", trip),
        _trip_html("Trip Starting Today", trip),
    )


def notify_trip_ended(trip):
    _send_email(
        _subject("Trip Ended", trip),
        _trip_html("Trip Ended", trip),
    )
