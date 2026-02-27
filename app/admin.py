from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.models import Person

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@login_required
def people_list():
    people = Person.query.order_by(Person.name).all()
    return render_template("admin/people.html", people=people)


@bp.route("/people/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_person(id):
    person = db.get_or_404(Person, id)
    if request.method == "POST":
        person.default_location_label = request.form["location_label"]
        person.default_location_lat = float(request.form["latitude"])
        person.default_location_lng = float(request.form["longitude"])
        db.session.commit()
        flash(f"Updated default location for {person.name}.", "success")
        return redirect(url_for("admin.people_list"))
    return render_template("admin/edit_person.html", person=person)
