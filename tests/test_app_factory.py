from app import create_app, _seed_people, db
from app.models import Person, Family


class TestCreateApp:
    def test_returns_flask_app(self):
        from flask import Flask
        app = create_app()
        assert isinstance(app, Flask)

    def test_registers_auth_blueprint(self, app):
        assert "auth" in app.blueprints

    def test_registers_trips_blueprint(self, app):
        assert "trips" in app.blueprints

    def test_registers_admin_blueprint(self, app):
        assert "admin" in app.blueprints

    def test_configures_login_view(self, app):
        from app import login_manager
        assert login_manager.login_view == "auth.login"

    def test_registers_cli_command(self, app):
        runner = app.test_cli_runner()
        # The command should exist and be invokable
        result = runner.invoke(args=["send-notifications"])
        assert result.exit_code == 0


class TestSeedPeople:
    def test_seeds_10_people(self, app):
        _seed_people()
        assert Person.query.count() == 10

    def test_seeds_with_colors(self, app):
        _seed_people()
        people = Person.query.order_by(Person.id).all()
        assert people[0].color == "#e6194b"
        assert people[1].color == "#3cb44b"

    def test_seeds_3_families(self, app):
        _seed_people()
        assert Family.query.count() == 3
        fam_names = {f.name for f in Family.query.all()}
        assert fam_names == {"Family A", "Family B", "Family C"}

    def test_noop_when_people_exist(self, app):
        _seed_people()
        assert Person.query.count() == 10
        _seed_people()
        assert Person.query.count() == 10
