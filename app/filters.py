from collections import OrderedDict

from markupsafe import Markup


def register_filters(app):
    """Register custom Jinja2 template filters."""

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
