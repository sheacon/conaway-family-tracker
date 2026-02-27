from collections import OrderedDict
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.models import Trip, Person, Family

bp = Blueprint("trips", __name__)


def _current_locations():
    """Return a list of dicts with each person's current location info."""
    today = date.today()
    people = Person.query.order_by(Person.name).all()
    locations = []
    for person in people:
        active_trip = (
            Trip.query.filter(
                Trip.people.any(id=person.id),
                Trip.start_date <= today,
                Trip.end_date >= today,
            ).first()
        )
        if active_trip:
            locations.append({
                "name": person.name,
                "label": active_trip.destination,
                "lat": active_trip.latitude,
                "lng": active_trip.longitude,
                "traveling": True,
                "color": person.color,
                "family": person.family.name if person.family else None,
                "family_sort": person.family.sort_order if person.family else 999,
            })
        else:
            locations.append({
                "name": person.name,
                "label": person.default_location_label,
                "lat": person.default_location_lat,
                "lng": person.default_location_lng,
                "traveling": False,
                "color": person.color,
                "family": person.family.name if person.family else None,
                "family_sort": person.family.sort_order if person.family else 999,
            })
    return locations


def _people_by_family():
    """Return an OrderedDict of family_name -> [Person] for the trip form."""
    people = Person.query.order_by(Person.name).all()
    groups = OrderedDict()
    sorted_people = sorted(people, key=lambda p: (p.family.sort_order if p.family else 999, p.name))
    for person in sorted_people:
        group_name = person.family.name if person.family else "Other"
        groups.setdefault(group_name, []).append(person)
    return groups


@bp.route("/")
@login_required
def index():
    today = date.today()
    locations = _current_locations()
    upcoming = (
        Trip.query.filter(Trip.start_date > today)
        .order_by(Trip.start_date)
        .all()
    )

    # Build family-grouped OrderedDict
    family_groups = OrderedDict()
    sorted_locs = sorted(locations, key=lambda l: (l["family_sort"], l["name"]))
    for loc in sorted_locs:
        group_name = loc["family"] or "Other"
        family_groups.setdefault(group_name, []).append(loc)

    return render_template(
        "index.html",
        locations=locations,
        family_groups=family_groups,
        upcoming=upcoming,
    )


@bp.route("/trips")
@login_required
def trip_list():
    trips = Trip.query.order_by(Trip.start_date).all()
    return render_template("trips.html", trips=trips)


@bp.route("/trips/new", methods=["GET", "POST"])
@login_required
def new_trip():
    if request.method == "POST":
        if not request.form.get("latitude") or not request.form.get("longitude"):
            flash("Please find the destination on the map before submitting.", "error")
            people_by_family = _people_by_family()
            return render_template("trip_form.html", trip=None, people_by_family=people_by_family)
        trip = Trip(
            destination=request.form["destination"],
            start_date=date.fromisoformat(request.form["start_date"]),
            end_date=date.fromisoformat(request.form["end_date"]),
            latitude=float(request.form["latitude"]),
            longitude=float(request.form["longitude"]),
        )
        person_ids = request.form.getlist("people")
        if person_ids:
            trip.people = Person.query.filter(Person.id.in_(person_ids)).all()
        db.session.add(trip)
        db.session.commit()
        flash("Trip added!", "success")
        return redirect(url_for("trips.trip_list"))
    people_by_family = _people_by_family()
    return render_template("trip_form.html", trip=None, people_by_family=people_by_family)


@bp.route("/trips/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_trip(id):
    trip = db.get_or_404(Trip, id)
    if request.method == "POST":
        if not request.form.get("latitude") or not request.form.get("longitude"):
            flash("Please find the destination on the map before submitting.", "error")
            people_by_family = _people_by_family()
            return render_template("trip_form.html", trip=trip, people_by_family=people_by_family)
        trip.destination = request.form["destination"]
        trip.start_date = date.fromisoformat(request.form["start_date"])
        trip.end_date = date.fromisoformat(request.form["end_date"])
        trip.latitude = float(request.form["latitude"])
        trip.longitude = float(request.form["longitude"])
        person_ids = request.form.getlist("people")
        trip.people = Person.query.filter(Person.id.in_(person_ids)).all() if person_ids else []
        db.session.commit()
        flash("Trip updated!", "success")
        return redirect(url_for("trips.trip_list"))
    people_by_family = _people_by_family()
    return render_template("trip_form.html", trip=trip, people_by_family=people_by_family)


@bp.route("/trips/<int:id>/delete", methods=["POST"])
@login_required
def delete_trip(id):
    trip = db.get_or_404(Trip, id)
    db.session.delete(trip)
    db.session.commit()
    flash("Trip deleted.", "success")
    return redirect(url_for("trips.trip_list"))
