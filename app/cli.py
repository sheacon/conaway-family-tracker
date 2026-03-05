from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import click
from flask.cli import with_appcontext

from app.models import Trip
from app.email import notify_trip_starting_soon, notify_trip_started, notify_trip_ended


@click.command("send-notifications")
@with_appcontext
def send_notifications():
    """Send daily email notifications for upcoming and ending trips."""
    today = datetime.now(ZoneInfo("America/New_York")).date()

    soon = today + timedelta(days=3)
    for trip in Trip.query.filter(Trip.start_date == soon).all():
        click.echo(f"Starting soon: {trip.display_name}")
        notify_trip_starting_soon(trip)

    for trip in Trip.query.filter(Trip.start_date == today).all():
        click.echo(f"Starting today: {trip.display_name}")
        notify_trip_started(trip)

    for trip in Trip.query.filter(Trip.end_date == today, Trip.start_date != today).all():
        click.echo(f"Ended today: {trip.display_name}")
        notify_trip_ended(trip)

    click.echo("Done.")
