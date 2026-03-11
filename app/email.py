import base64
import logging
from collections import OrderedDict
from datetime import datetime
from zoneinfo import ZoneInfo

import resend
from flask import current_app

from app import db
from app.filters import format_date, format_date_range
from app.models import Config, Person, Trip

logger = logging.getLogger(__name__)

BASE_URL = "https://conaway-family-tracker.fly.dev"


def notifications_paused() -> bool:
    """Return True if CRUD trip notifications are paused via admin toggle."""
    row = db.session.get(Config, "notifications_paused")
    return row is not None and row.value == "1"


def _get_recipients():
    return [p.email for p in Person.query.filter(Person.email.isnot(None)).all()]


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


def _send_email(subject: str, html_body: str, attachments: list[dict] | None = None):
    """Send an email to all recipients with email addresses."""
    recipients = _get_recipients()
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


def _get_map_attachment() -> dict | None:
    """Read the cached map PNG and return a Resend attachment dict, or None."""
    from app.map_generator import _cache_paths

    image_path, _ = _cache_paths()
    if not image_path.exists():
        return None
    try:
        data = image_path.read_bytes()
        return {
            "filename": "family-map.png",
            "content": base64.b64encode(data).decode("utf-8"),
            "content_type": "image/png",
            "content_id": "family-map",
        }
    except Exception:
        logger.exception("Failed to read map image for email attachment")
        return None


def _dashboard_html() -> tuple[str, dict | None]:
    """Generate dashboard HTML for email and optional map attachment."""
    from app.trips import _current_locations

    html = "<hr>"

    # --- Action Links ---
    html += "<p>"
    html += f'<a href="{BASE_URL}/trips/new">Add New Trip</a>'
    html += f' · <a href="{BASE_URL}/trips">View All Trips</a>'
    html += f' · <a href="{BASE_URL}/">View Dashboard</a>'
    html += "</p>"

    # --- Planned Trips ---
    today = datetime.now(ZoneInfo("America/New_York")).date()
    upcoming = Trip.query.filter(Trip.end_date >= today).order_by(Trip.start_date).all()

    if upcoming:
        html += "<h3>Planned Trips</h3>"
        html += '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; width: 100%;">'
        html += "<thead><tr><th>Trip</th><th>Who</th><th></th></tr></thead><tbody>"
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
            if trip.is_active:
                trip_cell += " <em>(in progress)</em>"
            trip_cell += f"<br><small>{format_date_range(trip.start_date, trip.end_date)}</small>"
            if trip.notes:
                trip_cell += f"<br><small><em>{trip.notes}</em></small>"

            # Transport mode icon + flight links
            mode = trip.transport_mode or "flying"
            mode_icons = {"flying": "✈️", "driving": "🚗", "train": "🚂", "boat": "🛳️"}
            icon = mode_icons.get(mode, "✈️")
            if mode == "flying" and (trip.outbound_flight or trip.return_flight):
                flight_parts = []
                if trip.outbound_flight:
                    links = ", ".join(
                        f'<a href="{Trip.flight_url(n.strip())}">{n.strip()}</a>'
                        for n in trip.outbound_flight.split(",")
                        if n.strip()
                    )
                    flight_parts.append(f"✈️ {links}")
                if trip.return_flight:
                    links = ", ".join(
                        f'<a href="{Trip.flight_url(n.strip())}">{n.strip()}</a>'
                        for n in trip.return_flight.split(",")
                        if n.strip()
                    )
                    flight_parts.append(f"✈️ {links}")
                trip_cell += f"<br><small>{' / '.join(flight_parts)}</small>"
            else:
                trip_cell += f"<br><small>{icon}</small>"

            # Who column
            people_sorted = sorted(
                trip.people,
                key=lambda p: (p.family.sort_order if p.family else 999, p.name),
            )
            who_cell = ", ".join(p.name for p in people_sorted) or "—"

            # Edit link
            edit_cell = f'<a href="{BASE_URL}/trips/{trip.id}/edit">Edit</a>'

            html += (
                f"<tr><td>{trip_cell}</td><td>{who_cell}</td><td>{edit_cell}</td></tr>"
            )
        html += "</tbody></table>"

    # --- Family Map ---
    map_attachment = _get_map_attachment()
    if map_attachment:
        html += "<h3>Family Map</h3>"
        html += '<img src="cid:family-map" alt="Conaway Family Map" style="width: 100%; max-width: 600px;">'

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
                    loc_cell += (
                        f"<br><small>✈️ {flight_links} ({flight['label']})</small>"
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

    return html, map_attachment


def _notify(subject: str, heading: str, trip):
    """Build trip-specific + dashboard HTML and send email."""
    trip_html = _trip_html(heading, trip)
    dashboard_html, map_attachment = _dashboard_html()
    full_html = trip_html + dashboard_html
    attachments = [map_attachment] if map_attachment else None
    _send_email(subject, full_html, attachments=attachments)


def notify_trip_created(trip):
    if notifications_paused():
        return
    _notify(_subject("New Trip", trip), "New Trip Added", trip)


def notify_trip_updated(trip):
    if notifications_paused():
        return
    _notify(_subject("Trip Updated", trip), "Trip Updated", trip)


def notify_trip_deleted(trip):
    if notifications_paused():
        return
    _notify(_subject("Trip Cancelled", trip), "Trip Cancelled", trip)


def notify_trip_starting_soon(trip):
    _notify(_subject("Trip in 3 Days", trip), "Trip Starting Soon", trip)


def notify_trip_started(trip):
    _notify(_subject("Trip Starting Today", trip), "Trip Starting Today", trip)


def notify_trip_ended(trip):
    _notify(_subject("Trip Ending", trip), "Trip Ending", trip)


def send_test_notification(recipient_email: str) -> bool:
    """Send a test email with dashboard content to a single recipient."""
    try:
        heading_html = "<h2>Test Notification</h2>"
        heading_html += "<p>This is a test email from the Conaway Family Tracker.</p>"
        dashboard_html, map_attachment = _dashboard_html()
        full_html = heading_html + dashboard_html
        attachments = [map_attachment] if map_attachment else None
        _send_email_to(
            [recipient_email],
            "Test Notification — Conaway Family Tracker",
            full_html,
            attachments=attachments,
        )
        return True
    except Exception:
        logger.exception("Failed to send test notification to %s", recipient_email)
        return False
