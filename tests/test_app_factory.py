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


class TestGroupByFamilyFilter:
    def test_groups_by_family_sorted(self, app, make_family, make_person, make_trip):
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

    def test_no_family_has_empty_key(self, app, make_person, make_trip):
        p = make_person(name="Solo")
        trip = make_trip(people=[p])
        filt = app.jinja_env.filters["group_by_family"]
        result = filt(trip.people)
        assert "" in result
        assert result[""] == ["Solo"]

    def test_empty_people(self, app, make_trip):
        trip = make_trip()
        filt = app.jinja_env.filters["group_by_family"]
        result = filt(trip.people)
        assert result == {}


class TestFlightLinkFilter:
    def test_single_flight(self, app):
        filt = app.jinja_env.filters["flight_link"]
        result = str(filt("UA100"))
        assert "flightaware.com/live/flight/UA100" in result
        assert ">UA100</a>" in result

    def test_comma_separated_flights(self, app):
        filt = app.jinja_env.filters["flight_link"]
        result = str(filt("UA100, AA200"))
        assert "flightaware.com/live/flight/UA100" in result
        assert "flightaware.com/live/flight/AA200" in result
        assert ">UA100</a>" in result
        assert ">AA200</a>" in result
        assert ", " in result

    def test_empty_string(self, app):
        filt = app.jinja_env.filters["flight_link"]
        assert filt("") == ""

    def test_none(self, app):
        filt = app.jinja_env.filters["flight_link"]
        assert filt(None) == ""
