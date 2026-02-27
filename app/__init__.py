from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from . import models  # noqa: F401
    from .auth import bp as auth_bp
    from .trips import bp as trips_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(trips_bp)

    # Seed default home config
    with app.app_context():
        _seed_home_config()

    return app


def _seed_home_config():
    from sqlalchemy import inspect
    from .models import Config as Cfg

    if not inspect(db.engine).has_table("config"):
        return

    if not db.session.get(Cfg, "home_label"):
        defaults = [
            Cfg(key="home_label", value="Home"),
            Cfg(key="home_lat", value="39.8283"),
            Cfg(key="home_lng", value="-98.5795"),
        ]
        db.session.add_all(defaults)
        db.session.commit()
