from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"

FAMILY_MEMBERS = [
    "Person A", "Person B", "Person C", "Person D", "Person E",
    "Person F", "Person G", "Person H", "Person I", "Person J",
]

COLOR_PALETTE = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990",
]

DEFAULT_FAMILIES = [
    ("Family A", ["Person A", "Person B"]),
    ("Family B", ["Person C", "Person D", "Person E", "Person F", "Person G"]),
    ("Family C", ["Person H", "Person I", "Person J"]),
]


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from . import models  # noqa: F401
    from .auth import bp as auth_bp
    from .trips import bp as trips_bp
    from .admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(trips_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        _seed_people()

    return app


def _seed_people():
    """Seed people, colors, and families. Uses raw SQL to survive pre-migration runs."""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if not inspector.has_table("person"):
        return

    person_cols = {c["name"] for c in inspector.get_columns("person")}
    has_color = "color" in person_cols
    has_family = inspector.has_table("family") and "family_id" in person_cols

    row = db.session.execute(text("SELECT id FROM person LIMIT 1")).fetchone()
    if row is not None:
        # Backfill colors on existing rows
        if has_color:
            rows = db.session.execute(
                text("SELECT id, color FROM person ORDER BY id")
            ).fetchall()
            for i, (pid, color) in enumerate(rows):
                if color == "#3388ff":
                    db.session.execute(
                        text("UPDATE person SET color = :c WHERE id = :id"),
                        {"c": COLOR_PALETTE[i % len(COLOR_PALETTE)], "id": pid},
                    )
            db.session.commit()

        # Backfill families
        if has_family:
            fam_count = db.session.execute(text("SELECT COUNT(*) FROM family")).scalar()
            if fam_count == 0:
                _seed_families(has_color)
        return

    # Fresh seed
    for i, name in enumerate(FAMILY_MEMBERS):
        if has_color:
            db.session.execute(
                text("INSERT INTO person (name, color) VALUES (:n, :c)"),
                {"n": name, "c": COLOR_PALETTE[i % len(COLOR_PALETTE)]},
            )
        else:
            db.session.execute(
                text("INSERT INTO person (name) VALUES (:n)"), {"n": name}
            )
    db.session.commit()

    if has_family:
        _seed_families(has_color)


def _seed_families(has_color):
    from sqlalchemy import text

    for order, (fname, member_names) in enumerate(DEFAULT_FAMILIES):
        db.session.execute(
            text("INSERT INTO family (name, sort_order) VALUES (:n, :o)"),
            {"n": fname, "o": order},
        )
        fam_id = db.session.execute(
            text("SELECT id FROM family WHERE name = :n"), {"n": fname}
        ).scalar()
        for mname in member_names:
            db.session.execute(
                text("UPDATE person SET family_id = :fid WHERE name = :n"),
                {"fid": fam_id, "n": mname},
            )
    db.session.commit()
