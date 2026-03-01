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
    from .admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(trips_bp)
    app.register_blueprint(admin_bp)

    from .cli import send_notifications
    app.cli.add_command(send_notifications)

    from .filters import register_filters
    register_filters(app)

    with app.app_context():
        from .seed import seed_people
        seed_people()

    return app
