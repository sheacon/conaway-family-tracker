from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, UserMixin

from app import login_manager

bp = Blueprint("auth", __name__)


class FamilyUser(UserMixin):
    def __init__(self):
        self.id = "family"


_user = FamilyUser()


@login_manager.user_loader
def load_user(user_id):
    if user_id == "family":
        return _user
    return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    from flask import current_app

    if request.method == "POST":
        password = request.form.get("password", "")
        if password == current_app.config["APP_PASSWORD"]:
            login_user(_user, remember=True)
            return redirect(request.args.get("next") or url_for("trips.index"))
        flash("Wrong password.", "error")
    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("trips.index"))
