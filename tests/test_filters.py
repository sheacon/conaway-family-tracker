"""Tests for Jinja2 template filters."""

from datetime import date

from freezegun import freeze_time
from markupsafe import Markup

from app.filters import format_date, format_date_range


class TestFormatDate:
    @freeze_time("2026-06-01", tz_offset=0)
    def test_current_year_omits_year(self):
        result = format_date(date(2026, 6, 15))
        assert "2026" not in result
        assert "Jun" in result
        assert "15" in result

    @freeze_time("2026-06-01", tz_offset=0)
    def test_different_year_includes_year(self):
        result = format_date(date(2027, 3, 10))
        assert "2027" in result
        assert "Mar" in result

    @freeze_time("2026-06-01", tz_offset=0)
    def test_includes_day_of_week(self):
        result = format_date(date(2026, 6, 1))  # Monday
        assert "Mon" in result


class TestFormatDateRange:
    @freeze_time("2026-06-01", tz_offset=0)
    def test_same_day(self):
        result = format_date_range(date(2026, 6, 15), date(2026, 6, 15))
        assert result == format_date(date(2026, 6, 15))

    @freeze_time("2026-06-01", tz_offset=0)
    def test_same_month_compact(self):
        result = format_date_range(date(2026, 6, 10), date(2026, 6, 15))
        assert "\u2013" in result or "–" in result
        # Should use compact end (no month repeated)
        parts = result.split("–")
        assert "Jun" in parts[0].strip()
        # End should not repeat the month
        assert "Jun" not in parts[1].strip()

    @freeze_time("2026-06-01", tz_offset=0)
    def test_different_months(self):
        result = format_date_range(date(2026, 6, 28), date(2026, 7, 5))
        assert "Jun" in result
        assert "Jul" in result

    @freeze_time("2026-06-01", tz_offset=0)
    def test_different_years(self):
        result = format_date_range(date(2026, 12, 28), date(2027, 1, 5))
        assert "2026" in result or "Dec" in result
        assert "2027" in result or "Jan" in result


class TestFlightLinkFilter:
    def test_iata_converts_to_link(self, app):
        flight_link = app.jinja_env.filters["flight_link"]
        result = flight_link("AA100")
        assert isinstance(result, Markup)
        assert "flightaware.com" in result
        assert "AAL100" in result
        assert 'target="_blank"' in result

    def test_multiple_flights(self, app):
        flight_link = app.jinja_env.filters["flight_link"]
        result = flight_link("AA100, DL200")
        assert "AAL100" in result
        assert "DAL200" in result

    def test_empty_string(self, app):
        flight_link = app.jinja_env.filters["flight_link"]
        assert flight_link("") == ""

    def test_none_returns_empty(self, app):
        flight_link = app.jinja_env.filters["flight_link"]
        assert flight_link(None) == ""


class TestGroupByFamilyFilter:
    def test_groups_people(self, app, make_family, make_person):
        group_by_family = app.jinja_env.filters["group_by_family"]
        f1 = make_family(name="Smith", sort_order=1)
        f2 = make_family(name="Jones", sort_order=2)
        make_person(name="Alice", family=f1)
        make_person(name="Bob", family=f2)
        from app.models import Person
        people = Person.query.all()
        groups = group_by_family(people)
        keys = list(groups.keys())
        assert "Smith" in keys
        assert "Jones" in keys

    def test_sorts_by_family_order(self, app, make_family, make_person):
        group_by_family = app.jinja_env.filters["group_by_family"]
        f2 = make_family(name="Second", sort_order=2)
        f1 = make_family(name="First", sort_order=1)
        make_person(name="Alice", family=f2)
        make_person(name="Bob", family=f1)
        from app.models import Person
        people = Person.query.all()
        groups = group_by_family(people)
        keys = list(groups.keys())
        assert keys.index("First") < keys.index("Second")

    def test_unfamilied_at_end(self, app, make_family, make_person):
        group_by_family = app.jinja_env.filters["group_by_family"]
        f = make_family(name="Smith", sort_order=1)
        make_person(name="Alice", family=f)
        make_person(name="Orphan")
        from app.models import Person
        people = Person.query.all()
        groups = group_by_family(people)
        keys = list(groups.keys())
        assert keys[-1] == ""
