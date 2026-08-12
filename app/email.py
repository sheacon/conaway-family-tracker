import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import resend
from flask import current_app

from app import db
from app.filters import format_date, format_date_range
from app.models import Config, Person, Trip

logger = logging.getLogger(__name__)

BASE_URL = "https://conaway-family-tracker.fly.dev"

NOTIFICATION_TYPES = [
    {"key": "trip_created", "label": "Trip Created"},
    {"key": "trip_updated", "label": "Trip Updated"},
    {"key": "trip_deleted", "label": "Trip Cancelled"},
    {"key": "trip_starting_soon", "label": "Starting Soon (3 days)"},
    {"key": "trip_started", "label": "Trip Starting Today"},
    {"key": "trip_ended", "label": "Trip Ending Today"},
]


def notifications_paused() -> bool:
    """Return True if CRUD trip notifications are paused via admin toggle."""
    row = db.session.get(Config, "notifications_paused")
    return row is not None and row.value == "1"


def _get_recipients(notification_type: str | None = None) -> list[str]:
    people = Person.query.filter(Person.email.isnot(None)).all()
    if notification_type is None:
        return [p.email for p in people]
    return [
        p.email for p in people
        if notification_type in p.get_enabled_notifications()
    ]


def _send_email_to(
    recipients: list[str],
    subject: str,
    html_body: str,
    attachments: list[dict] | None = None,
):
    """Send an email to specific recipients."""
    api_key = current_app.config.get("RESEND_API_KEY")
    if not api_key:
        return
    if not recipients:
        return
    resend.api_key = api_key
    payload = {
        "from": current_app.config["RESEND_FROM_EMAIL"],
        "to": recipients,
        "subject": subject,
        "html": html_body,
    }
    if attachments:
        payload["attachments"] = attachments
    try:
        resend.Emails.send(payload)
    except Exception:
        logger.exception("Failed to send email: %s", subject)


def _send_email(
    subject: str,
    html_body: str,
    attachments: list[dict] | None = None,
    notification_type: str | None = None,
):
    """Send an email to all recipients with email addresses."""
    recipients = _get_recipients(notification_type=notification_type)
    if not recipients:
        return
    _send_email_to(recipients, subject, html_body, attachments=attachments)


def _format_people(trip):
    return ", ".join(p.name for p in trip.people) or "No one assigned"


def _format_dates(trip):
    return format_date_range(trip.start_date, trip.end_date)


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
            html += f"<li>{stop.destination}: {format_date(stop.start_date)} – {format_date(stop.end_date)}</li>"
        html += "</ol>"
    else:
        html += f"<p><strong>Destination:</strong> {trip.destination}</p>"
    html += f"<p><strong>Who:</strong> {_format_people(trip)}</p>"
    html += f"<p><strong>When:</strong> {_format_dates(trip)}</p>"
    if trip.notes:
        html += f"<p><strong>Notes:</strong> {trip.notes}</p>"
    if trip.outbound_flight or trip.return_flight:
        parts = []
        if trip.outbound_flight:
            links = ", ".join(
                f'<a href="{Trip.flight_url(n.strip())}">{n.strip()}</a>'
                for n in trip.outbound_flight.split(",")
                if n.strip()
            )
            parts.append(f"Outbound: {links}")
        if trip.return_flight:
            links = ", ".join(
                f'<a href="{Trip.flight_url(n.strip())}">{n.strip()}</a>'
                for n in trip.return_flight.split(",")
                if n.strip()
            )
            parts.append(f"Return: {links}")
        html += f"<p><strong>Flights:</strong> {' / '.join(parts)}</p>"
    return html


def _map_image_url() -> str | None:
    """Return the public URL of the map image, or None if no map is cached.

    Served over HTTPS rather than embedded as a cid: attachment — webmail
    clients (Gmail) do not reliably resolve cid: references. The ?v= content
    hash busts Gmail's image-proxy cache when the map regenerates.
    """
    from app.map_generator import map_token, map_version

    version = map_version()
    if version is None:
        return None
    return f"{BASE_URL}/map/{map_token()}.jpg?v={version}"


def _dashboard_html() -> str:
    """Generate dashboard HTML for email."""
    from app.trips import _current_locations

    html = "<hr>"

    # --- Action Links ---
    html += "<p>"
    html += f'<a href="{BASE_URL}/trips/new">Add New Trip</a>'
    html += f' · <a href="{BASE_URL}/trips">View All Trips</a>'
    html += f' · <a href="{BASE_URL}/">View Dashboard</a>'
    html += "</p>"

    # --- Upcoming Trips (within 2 months) ---
    today = datetime.now(ZoneInfo("America/New_York")).date()
    two_months = today + timedelta(days=60)
    upcoming = Trip.query.filter(Trip.end_date >= today, Trip.start_date <= two_months).order_by(Trip.start_date).all()

    if upcoming:
        html += "<h3>Upcoming Trips</h3>"
        html += '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; width: 100%;">'
        html += "<thead><tr><th>Trip</th><th>Dates</th><th>Who</th><th>Mode</th><th></th></tr></thead><tbody>"
        for trip in upcoming:
            # Trip column
            trip_cell = ""
            if trip.title:
                trip_cell += f"<strong>{trip.title}</strong><br>"
                trip_cell += f"<small>{trip.destinations_summary if trip.is_multi_stop else trip.destination}</small>"
            else:
                trip_cell += (
                    trip.destinations_summary
                    if trip.is_multi_stop
                    else trip.destination
                )
            if trip.notes:
                trip_cell += f"<br><small><em>{trip.notes}</em></small>"

            # Dates column
            dates_cell = format_date_range(trip.start_date, trip.end_date)
            if trip.is_active:
                dates_cell += " <em>(in progress)</em>"

            # Travel column
            mode = trip.transport_mode or "flying"
            mode_icons = {"flying": "🛫", "driving": "🚗", "train": "🚂", "boat": "🛳️"}
            icon = mode_icons.get(mode, "✈️")
            if mode == "flying" and (trip.outbound_flight or trip.return_flight):
                flight_parts = []
                if trip.outbound_flight:
                    links = ", ".join(
                        f'<a href="{Trip.flight_url(n.strip())}">{n.strip()}</a>'
                        for n in trip.outbound_flight.split(",")
                        if n.strip()
                    )
                    flight_parts.append(f"🛫 {links}")
                if trip.return_flight:
                    links = ", ".join(
                        f'<a href="{Trip.flight_url(n.strip())}">{n.strip()}</a>'
                        for n in trip.return_flight.split(",")
                        if n.strip()
                    )
                    flight_parts.append(f"🛬 {links}")
                travel_cell = " / ".join(flight_parts)
            else:
                travel_cell = icon

            # Who column
            people_sorted = sorted(
                trip.people,
                key=lambda p: (p.family.sort_order if p.family else 999, p.name),
            )
            who_cell = ", ".join(p.name for p in people_sorted) or "—"

            # Edit link
            edit_cell = f'<a href="{BASE_URL}/trips/{trip.id}/edit">Edit</a>'

            html += (
                f"<tr><td>{trip_cell}</td><td>{dates_cell}</td><td>{who_cell}</td><td>{travel_cell}</td><td>{edit_cell}</td></tr>"
            )
        html += "</tbody></table>"

    # --- Family Map ---
    map_url = _map_image_url()
    if map_url:
        html += "<h3>Family Map</h3>"
        html += (
            f'<img src="{map_url}" alt="Conaway Family Map" '
            f'width="600" style="width: 100%; max-width: 600px;">'
        )

    # --- Current Locations ---
    locations = _current_locations()
    if locations:
        family_groups: OrderedDict[str, list[dict]] = OrderedDict()
        sorted_locs = sorted(
            locations, key=lambda loc: (loc["family_sort"], loc["name"])
        )
        for loc in sorted_locs:
            group_name = loc["family"] or "Other"
            family_groups.setdefault(group_name, []).append(loc)

        html += "<h3>Current Locations</h3>"
        html += '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; width: 100%;">'
        html += "<thead><tr><th>Name</th><th>Current Location</th><th>Next Trip</th></tr></thead>"
        for family_name, members in family_groups.items():
            html += f'<tbody><tr><th colspan="3">{family_name}</th></tr>'
            for loc in members:
                # Name
                name_cell = loc["name"]

                # Current Location
                loc_cell = loc["label"]
                if loc.get("travel_day"):
                    loc_cell += " <em>(in transit)</em>"
                elif loc.get("traveling"):
                    loc_cell += " <em>(traveling)</em>"
                if loc.get("traveling"):
                    trip_dest = loc.get("trip_destination", "")
                    if trip_dest and trip_dest != loc["label"]:
                        loc_cell += f"<br><small>{trip_dest}</small>"
                    loc_cell += f"<br><small>{loc.get('trip_dates', '')}</small>"
                if loc.get("stop_info"):
                    loc_cell += f"<br><small>{loc['stop_info']}</small>"
                if loc.get("flight"):
                    flight = loc["flight"]
                    flight_links = ", ".join(
                        f'<a href="{Trip.flight_url(n.strip())}">{n.strip()}</a>'
                        for n in flight["number"].split(",")
                        if n.strip()
                    )
                    flight_icon = "🛫" if flight["label"] == "Outbound" else "🛬"
                    loc_cell += (
                        f"<br><small>{flight_icon} {flight_links} ({flight['label']})</small>"
                    )

                # Next Trip
                next_cell = "—"
                nt = loc.get("next_trip")
                if nt:
                    if nt.get("title"):
                        next_cell = (
                            f"{nt['title']}<br><small>{nt['destination']}</small>"
                        )
                    else:
                        next_cell = nt["destination"]
                    next_cell += f"<br><small>{nt['dates']}</small>"
                    if nt.get("notes"):
                        next_cell += f"<br><small><em>{nt['notes']}</em></small>"

                html += f"<tr><td>{name_cell}</td><td>{loc_cell}</td><td>{next_cell}</td></tr>"
            html += "</tbody>"
        html += "</table>"

    return html


def _notify(subject: str, heading: str, trip, notification_type: str | None = None):
    """Build trip-specific + dashboard HTML and send email."""
    full_html = _trip_html(heading, trip) + _dashboard_html()
    _send_email(subject, full_html, notification_type=notification_type)


def notify_trip_created(trip):
    if notifications_paused():
        return
    _notify(_subject("New Trip", trip), "New Trip Added", trip, notification_type="trip_created")


def notify_trip_updated(trip):
    if notifications_paused():
        return
    _notify(_subject("Trip Updated", trip), "Trip Updated", trip, notification_type="trip_updated")


def notify_trip_deleted(trip):
    if notifications_paused():
        return
    _notify(_subject("Trip Cancelled", trip), "Trip Cancelled", trip, notification_type="trip_deleted")


def notify_trip_starting_soon(trip):
    _notify(_subject("Trip in 3 Days", trip), "Trip Starting Soon", trip, notification_type="trip_starting_soon")


def notify_trip_started(trip):
    _notify(_subject("Trip Starting Today", trip), "Trip Starting Today", trip, notification_type="trip_started")


def notify_trip_ended(trip):
    _notify(_subject("Trip Ending", trip), "Trip Ending", trip, notification_type="trip_ended")


def send_test_notification(recipient_email: str) -> bool:
    """Send a test email with dashboard content to a single recipient."""
    try:
        heading_html = "<h2>Test Notification</h2>"
        heading_html += "<p>This is a test email from the Conaway Family Tracker.</p>"
        full_html = heading_html + _dashboard_html()
        _send_email_to(
            [recipient_email],
            "Test Notification — Conaway Family Tracker",
            full_html,
        )
        return True
    except Exception:
        logger.exception("Failed to send test notification to %s", recipient_email)
        return False
