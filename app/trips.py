from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.models import Trip, Config

bp = Blueprint("trips", __name__)


def _home_location():
    label = db.session.get(Config, "home_label")
    lat = db.session.get(Config, "home_lat")
    lng = db.session.get(Config, "home_lng")
    return {
        "label": label.value if label else "Home",
        "lat": float(lat.value) if lat else 39.8283,
        "lng": float(lng.value) if lng else -98.5795,
    }


@bp.route("/")
def index():
    today = date.today()
    active = Trip.query.filter(Trip.start_date <= today, Trip.end_date >= today).first()
    upcoming = (
        Trip.query.filter(Trip.start_date > today)
        .order_by(Trip.start_date)
        .all()
    )
    home = _home_location()
    return render_template(
        "index.html", active=active, upcoming=upcoming, home=home
    )


@bp.route("/trips")
@login_required
def trip_list():
    trips = Trip.query.order_by(Trip.start_date.desc()).all()
    return render_template("trips.html", trips=trips)


@bp.route("/trips/new", methods=["GET", "POST"])
@login_required
def new_trip():
    if request.method == "POST":
        trip = Trip(
            destination=request.form["destination"],
            start_date=date.fromisoformat(request.form["start_date"]),
            end_date=date.fromisoformat(request.form["end_date"]),
            latitude=float(request.form["latitude"]),
            longitude=float(request.form["longitude"]),
        )
        db.session.add(trip)
        db.session.commit()
        flash("Trip added!", "success")
        return redirect(url_for("trips.trip_list"))
    return render_template("trip_form.html", trip=None)


@bp.route("/trips/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_trip(id):
    trip = db.get_or_404(Trip, id)
    if request.method == "POST":
        trip.destination = request.form["destination"]
        trip.start_date = date.fromisoformat(request.form["start_date"])
        trip.end_date = date.fromisoformat(request.form["end_date"])
        trip.latitude = float(request.form["latitude"])
        trip.longitude = float(request.form["longitude"])
        db.session.commit()
        flash("Trip updated!", "success")
        return redirect(url_for("trips.trip_list"))
    return render_template("trip_form.html", trip=trip)


@bp.route("/trips/<int:id>/delete", methods=["POST"])
@login_required
def delete_trip(id):
    trip = db.get_or_404(Trip, id)
    db.session.delete(trip)
    db.session.commit()
    flash("Trip deleted.", "success")
    return redirect(url_for("trips.trip_list"))
