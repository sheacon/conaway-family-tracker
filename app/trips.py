from collections import OrderedDict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.models import Trip, TripStop, Person, Family, TripPersonFlight
from app.email import notify_trip_created, notify_trip_updated, notify_trip_deleted

bp = Blueprint("trips", __name__)


def _current_locations():
    """Return a list of dicts with each person's current location info."""
    today = date.today()
    people = Person.query.order_by(Person.name).all()
    locations = []
    for person in people:
        active_trips = (
            Trip.query.filter(
                Trip.people.any(id=person.id),
                Trip.start_date <= today,
                Trip.end_date >= today,
            )
            .order_by(Trip.start_date)
            .all()
        )
        if len(active_trips) > 1:
            now_et = datetime.now(ZoneInfo("America/New_York"))
            active_trip = active_trips[0] if now_et.hour < 12 else active_trips[-1]
        else:
            active_trip = active_trips[0] if active_trips else None
        next_trip = (
            Trip.query.filter(
                Trip.people.any(id=person.id),
                Trip.start_date > today,
            )
            .order_by(Trip.start_date)
            .first()
        )
        next_trip_info = None
        if next_trip:
            next_trip_info = {
                "display_name": next_trip.display_name,
                "destination": next_trip.destination,
                "title": next_trip.title,
                "notes": next_trip.notes,
                "dates": f"{next_trip.start_date.strftime('%b %-d')} – {next_trip.end_date.strftime('%b %-d')}",
            }
        flight = None
        if active_trip:
            fi = active_trip.flight_for_person(person.id)
            if fi:
                if active_trip.start_date == active_trip.end_date:
                    now_et = datetime.now(ZoneInfo("America/New_York"))
                    if now_et.hour < 12 and fi.outbound_flight:
                        flight = {"number": fi.outbound_flight, "label": "Outbound"}
                    elif now_et.hour >= 12 and fi.return_flight:
                        flight = {"number": fi.return_flight, "label": "Return"}
                elif today == active_trip.start_date and fi.outbound_flight:
                    flight = {"number": fi.outbound_flight, "label": "Outbound"}
                elif today == active_trip.end_date and fi.return_flight:
                    flight = {"number": fi.return_flight, "label": "Return"}

            # Use current stop coordinates for multi-stop trips
            current_stop = active_trip.current_stop(today)
            loc_lat = current_stop.latitude if current_stop else active_trip.latitude
            loc_lng = current_stop.longitude if current_stop else active_trip.longitude

            stop_info = None
            if active_trip.is_multi_stop and current_stop:
                stop_num = next(
                    (i + 1 for i, s in enumerate(active_trip.stops) if s.id == current_stop.id), 1
                )
                stop_info = f"{current_stop.destination} (Stop {stop_num} of {len(active_trip.stops)})"

            locations.append({
                "name": person.name,
                "label": active_trip.display_name,
                "lat": loc_lat,
                "lng": loc_lng,
                "traveling": True,
                "color": person.color,
                "family": person.family.name if person.family else None,
                "family_sort": person.family.sort_order if person.family else 999,
                "next_trip": next_trip_info,
                "flight": flight,
                "stop_info": stop_info,
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
                "next_trip": next_trip_info,
                "flight": None,
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


def _parse_stops_from_form():
    """Parse stop data from indexed form fields. Returns list of TripStop or None on error."""
    stop_count = int(request.form.get("stop_count", 1))
    stops = []
    for i in range(stop_count):
        lat = request.form.get(f"stop_latitude_{i}")
        lng = request.form.get(f"stop_longitude_{i}")
        if not lat or not lng:
            return None
        stops.append(TripStop(
            order=i,
            destination=request.form.get(f"stop_destination_{i}", ""),
            latitude=float(lat),
            longitude=float(lng),
            start_date=date.fromisoformat(request.form[f"stop_start_date_{i}"]),
            end_date=date.fromisoformat(request.form[f"stop_end_date_{i}"]),
        ))
    return stops


@bp.route("/trips/new", methods=["GET", "POST"])
@login_required
def new_trip():
    if request.method == "POST":
        stops = _parse_stops_from_form()
        if not stops:
            flash("Please confirm the location for all stops before submitting.", "error")
            people_by_family = _people_by_family()
            return render_template("trip_form.html", trip=None, people_by_family=people_by_family, flight_data={}, stops_data=[])
        trip = Trip(
            destination=stops[0].destination,
            title=request.form.get("title") or None,
            notes=request.form.get("notes") or None,
            start_date=stops[0].start_date,
            end_date=stops[-1].end_date,
            latitude=stops[0].latitude,
            longitude=stops[0].longitude,
        )
        for stop in stops:
            trip.stops.append(stop)
        person_ids = request.form.getlist("people")
        if person_ids:
            trip.people = Person.query.filter(Person.id.in_(person_ids)).all()
        db.session.add(trip)
        db.session.flush()
        for pid in person_ids:
            outbound = request.form.get(f"outbound_flight_{pid}", "").strip() or None
            ret = request.form.get(f"return_flight_{pid}", "").strip() or None
            if outbound or ret:
                db.session.add(TripPersonFlight(
                    trip_id=trip.id, person_id=int(pid),
                    outbound_flight=outbound, return_flight=ret,
                ))
        db.session.commit()
        notify_trip_created(trip)
        flash("Trip added!", "success")
        return redirect(url_for("trips.trip_list"))
    people_by_family = _people_by_family()
    return render_template("trip_form.html", trip=None, people_by_family=people_by_family, flight_data={}, stops_data=[])


@bp.route("/trips/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_trip(id):
    trip = db.get_or_404(Trip, id)
    if request.method == "POST":
        stops = _parse_stops_from_form()
        if not stops:
            flash("Please confirm the location for all stops before submitting.", "error")
            people_by_family = _people_by_family()
            flight_data = {str(fi.person_id): {"outbound": fi.outbound_flight or "", "return": fi.return_flight or ""} for fi in trip.flight_info}
            stops_data = [{"destination": s.destination, "latitude": s.latitude, "longitude": s.longitude,
                           "start_date": s.start_date.isoformat(), "end_date": s.end_date.isoformat()} for s in trip.stops]
            return render_template("trip_form.html", trip=trip, people_by_family=people_by_family, flight_data=flight_data, stops_data=stops_data)
        trip.title = request.form.get("title") or None
        trip.notes = request.form.get("notes") or None
        # Delete existing stops and re-create
        TripStop.query.filter_by(trip_id=trip.id).delete()
        for stop in stops:
            stop.trip_id = trip.id
            db.session.add(stop)
        db.session.flush()
        # Sync denormalized fields
        trip.destination = stops[0].destination
        trip.latitude = stops[0].latitude
        trip.longitude = stops[0].longitude
        trip.start_date = stops[0].start_date
        trip.end_date = stops[-1].end_date
        person_ids = request.form.getlist("people")
        trip.people = Person.query.filter(Person.id.in_(person_ids)).all() if person_ids else []
        TripPersonFlight.query.filter_by(trip_id=trip.id).delete()
        for pid in person_ids:
            outbound = request.form.get(f"outbound_flight_{pid}", "").strip() or None
            ret = request.form.get(f"return_flight_{pid}", "").strip() or None
            if outbound or ret:
                db.session.add(TripPersonFlight(
                    trip_id=trip.id, person_id=int(pid),
                    outbound_flight=outbound, return_flight=ret,
                ))
        db.session.commit()
        notify_trip_updated(trip)
        flash("Trip updated!", "success")
        return redirect(url_for("trips.trip_list"))
    people_by_family = _people_by_family()
    flight_data = {str(fi.person_id): {"outbound": fi.outbound_flight or "", "return": fi.return_flight or ""} for fi in trip.flight_info}
    stops_data = [{"destination": s.destination, "latitude": s.latitude, "longitude": s.longitude,
                   "start_date": s.start_date.isoformat(), "end_date": s.end_date.isoformat()} for s in trip.stops]
    return render_template("trip_form.html", trip=trip, people_by_family=people_by_family, flight_data=flight_data, stops_data=stops_data)


@bp.route("/trips/<int:id>/delete", methods=["POST"])
@login_required
def delete_trip(id):
    trip = db.get_or_404(Trip, id)
    notify_trip_deleted(trip)
    db.session.delete(trip)
    db.session.commit()
    flash("Trip deleted.", "success")
    return redirect(url_for("trips.trip_list"))
