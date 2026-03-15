from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.email import NOTIFICATION_TYPES, send_test_notification
from app.models import Config, Person, Family

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@login_required
def people_list():
    people = Person.query.order_by(Person.name).all()
    families = Family.query.order_by(Family.sort_order).all()
    row = db.session.get(Config, "notifications_paused")
    paused = row is not None and row.value == "1"
    return render_template(
        "admin/people.html",
        people=people,
        families=families,
        notifications_paused=paused,
        notification_types=NOTIFICATION_TYPES,
    )


@bp.route("/test-email", methods=["POST"])
@login_required
def send_test_email():
    email = request.form.get("email", "").strip()
    if not email:
        flash("Please select a recipient.", "error")
        return redirect(url_for("admin.people_list"))
    if send_test_notification(email):
        flash(f"Test email sent to {email}.", "success")
    else:
        flash("Failed to send test email.", "error")
    return redirect(url_for("admin.people_list"))


@bp.route("/notifications/toggle", methods=["POST"])
@login_required
def toggle_notifications():
    row = db.session.get(Config, "notifications_paused")
    if row is None:
        db.session.add(Config(key="notifications_paused", value="1"))
    else:
        row.value = "0" if row.value == "1" else "1"
    db.session.commit()
    return redirect(url_for("admin.people_list"))



@bp.route("/people/new", methods=["POST"])
@login_required
def new_person():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Name is required.", "error")
        return redirect(url_for("admin.people_list"))
    if Person.query.filter_by(name=name).first():
        flash("A person with that name already exists.", "error")
        return redirect(url_for("admin.people_list"))
    person = Person(name=name)
    email = request.form.get("email", "").strip()
    if email:
        person.email = email
    fam_id = request.form.get("family_id")
    if fam_id:
        person.family_id = int(fam_id)
    db.session.add(person)
    db.session.commit()
    flash(f"Added {name}.", "success")
    return redirect(url_for("admin.edit_person", id=person.id))


@bp.route("/people/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_person(id):
    person = db.get_or_404(Person, id)
    if request.method == "POST":
        person.default_location_label = request.form["location_label"]
        person.default_location_lat = float(request.form["latitude"])
        person.default_location_lng = float(request.form["longitude"])
        person.email = request.form.get("email", "").strip() or None
        fam_id = request.form.get("family_id")
        person.family_id = int(fam_id) if fam_id else None
        valid_keys = {t["key"] for t in NOTIFICATION_TYPES}
        selected = [k for k in request.form.getlist("notifications") if k in valid_keys]
        person.set_enabled_notifications(selected)
        db.session.commit()
        flash(f"Updated {person.name}.", "success")
        return redirect(url_for("admin.people_list"))
    families = Family.query.order_by(Family.sort_order).all()
    return render_template(
        "admin/edit_person.html",
        person=person,
        families=families,
        notification_types=NOTIFICATION_TYPES,
    )


# --- Family CRUD ---


@bp.route("/families")
@login_required
def family_list():
    families = Family.query.order_by(Family.sort_order).all()
    return render_template("admin/families.html", families=families)


@bp.route("/families/new", methods=["POST"])
@login_required
def new_family():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Family name is required.", "error")
        return redirect(url_for("admin.family_list"))
    if Family.query.filter_by(name=name).first():
        flash("A family with that name already exists.", "error")
        return redirect(url_for("admin.family_list"))
    max_order = db.session.query(db.func.max(Family.sort_order)).scalar() or 0
    db.session.add(Family(name=name, sort_order=max_order + 1))
    db.session.commit()
    flash(f"Created family '{name}'.", "success")
    return redirect(url_for("admin.family_list"))


@bp.route("/families/<int:id>/edit", methods=["POST"])
@login_required
def edit_family(id):
    family = db.get_or_404(Family, id)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Family name is required.", "error")
        return redirect(url_for("admin.family_list"))
    family.name = name
    db.session.commit()
    flash(f"Renamed family to '{name}'.", "success")
    return redirect(url_for("admin.family_list"))


@bp.route("/families/<int:id>/delete", methods=["POST"])
@login_required
def delete_family(id):
    family = db.get_or_404(Family, id)
    for member in family.members:
        member.family_id = None
    db.session.delete(family)
    db.session.commit()
    flash(f"Deleted family '{family.name}'.", "success")
    return redirect(url_for("admin.family_list"))
