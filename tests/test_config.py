"""Tests for app configuration and factory."""

from app import create_app, db


class TestConfig:
    def test_default_secret_key(self, app):
        assert app.config["SECRET_KEY"] == "dev-secret-change-me" or app.config["SECRET_KEY"]

    def test_app_password_from_env(self, app):
        assert app.config["APP_PASSWORD"] == "testpass"

    def test_database_url_from_env(self, app):
        assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite://"

    def test_resend_api_key_from_env(self, app):
        assert app.config["RESEND_API_KEY"] == "test-key"

    def test_resend_from_email_from_env(self, app):
        assert app.config["RESEND_FROM_EMAIL"] == "test@example.com"


class TestAppFactory:
    def test_create_app_returns_flask_app(self):
        app = create_app()
        assert app is not None
        assert app.name == "app"

    def test_blueprints_registered(self, app):
        assert "auth" in app.blueprints
        assert "trips" in app.blueprints
        assert "admin" in app.blueprints

    def test_cli_commands_registered(self, app):
        runner = app.test_cli_runner()
        # Verify commands exist by invoking --help
        result = runner.invoke(args=["send-notifications", "--help"])
        assert result.exit_code == 0
        result = runner.invoke(args=["generate-map", "--help"])
        assert result.exit_code == 0

    def test_filters_registered(self, app):
        assert "format_date" in app.jinja_env.filters
        assert "date_range" in app.jinja_env.filters
        assert "flight_link" in app.jinja_env.filters
        assert "group_by_family" in app.jinja_env.filters

    def test_seed_function_creates_people(self, app):
        from app.models import Person
        from app.seed import seed_people
        # Tables exist (created by fixture) but no people yet
        assert Person.query.count() == 0
        seed_people()
        assert Person.query.count() == 10

    def test_seed_is_idempotent(self, app):
        from app.models import Person
        from app.seed import seed_people
        seed_people()
        seed_people()
        assert Person.query.count() == 10
