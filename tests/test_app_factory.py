from flask import Flask

from app import create_app, db
from app.models import Person, Family
from app.seed import seed_people


class TestCreateApp:
    def test_returns_flask_app(self):
        app = create_app()
        assert isinstance(app, Flask)

    def test_registers_blueprints(self, app):
        assert "auth" in app.blueprints
        assert "trips" in app.blueprints
        assert "admin" in app.blueprints

    def test_configures_login_view(self, app):
        from app import login_manager
        assert login_manager.login_view == "auth.login"

    def test_registers_cli_command(self, app):
        runner = app.test_cli_runner()
        result = runner.invoke(args=["send-notifications"])
        assert result.exit_code == 0


class TestSeedPeople:
    def test_seeds_10_people(self, app):
        seed_people()
        assert Person.query.count() == 10

    def test_seeds_3_families(self, app):
        seed_people()
        assert Family.query.count() == 3
        names = {f.name for f in Family.query.all()}
        assert names == {"Family A", "Family B", "Family C"}

    def test_idempotent(self, app):
        seed_people()
        seed_people()
        assert Person.query.count() == 10
        assert Family.query.count() == 3


class TestFlightLinkFilter:
    def test_single_flight(self, app):
        filt = app.jinja_env.filters["flight_link"]
        result = str(filt("UA100"))
        assert "flightaware.com/live/flight/UAL100" in result
        assert ">UA100</a>" in result

    def test_comma_separated(self, app):
        filt = app.jinja_env.filters["flight_link"]
        result = str(filt("UA100, AA200"))
        assert "UAL100" in result
        assert "AAL200" in result

    def test_empty_string(self, app):
        assert app.jinja_env.filters["flight_link"]("") == ""

    def test_none(self, app):
        assert app.jinja_env.filters["flight_link"](None) == ""


class TestGroupByFamilyFilter:
    def test_groups_sorted_by_family(self, app, make_family, make_person, make_trip):
        f1 = make_family(name="Alpha", sort_order=1)
        f2 = make_family(name="Beta", sort_order=2)
        p1 = make_person(name="Zoe", family=f1)
        p2 = make_person(name="Amy", family=f2)
        p3 = make_person(name="Ben", family=f1)
        trip = make_trip(people=[p2, p1, p3])
        filt = app.jinja_env.filters["group_by_family"]
        result = filt(trip.people)
        keys = list(result.keys())
        assert keys == ["Alpha", "Beta"]
        assert result["Alpha"] == ["Ben", "Zoe"]
        assert result["Beta"] == ["Amy"]

    def test_no_family_uses_empty_key(self, app, make_person, make_trip):
        p = make_person(name="Solo")
        trip = make_trip(people=[p])
        result = app.jinja_env.filters["group_by_family"](trip.people)
        assert "" in result

    def test_empty_people(self, app, make_trip):
        trip = make_trip()
        result = app.jinja_env.filters["group_by_family"](trip.people)
        assert result == {}
