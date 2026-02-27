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
    from sqlalchemy import inspect
    from .models import Person

    if not inspect(db.engine).has_table("person"):
        return

    if Person.query.first() is not None:
        return

    for name in FAMILY_MEMBERS:
        db.session.add(Person(name=name))
    db.session.commit()
