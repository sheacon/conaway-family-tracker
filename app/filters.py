from collections import OrderedDict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from markupsafe import Markup


def _format_date(d):
    """Format a date with day-of-week, omitting year if it's the current year."""
    today = datetime.now(ZoneInfo("America/New_York")).date()
    if d.year == today.year:
        return d.strftime("%a, %b %-d")
    return d.strftime("%a, %b %-d, %Y")


def format_date_range(start_date, end_date):
    """Format a date range, omitting year for current-year dates."""
    return f"{_format_date(start_date)} – {_format_date(end_date)}"


def register_filters(app):
    """Register custom Jinja2 template filters."""

    @app.template_filter("format_date")
    def format_date_filter(d):
        return _format_date(d)

    @app.template_filter("date_range")
    def date_range_filter(trip):
        return format_date_range(trip.start_date, trip.end_date)

    @app.template_filter("flight_link")
    def flight_link(flight_number: str) -> str:
        if not flight_number:
            return ""
        from app.models import Trip

        parts = [n.strip() for n in flight_number.split(",")]
        links = [
            f'<a href="{Trip.flight_url(n)}" target="_blank">{n}</a>'
            for n in parts
            if n
        ]
        return Markup(", ".join(links))

    @app.template_filter("group_by_family")
    def group_by_family(people) -> OrderedDict:
        groups: OrderedDict[str, list[str]] = OrderedDict()
        for p in sorted(
            people,
            key=lambda p: (p.family.sort_order if p.family else 999, p.name),
        ):
            key = p.family.name if p.family else ""
            groups.setdefault(key, []).append(p.name)
        return groups
