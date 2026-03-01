from sqlalchemy import inspect

from app import db
from app.models import Family, Person

FAMILY_MEMBERS = [
    "Person A", "Person B", "Person C", "Person D", "Person E",
    "Person F", "Person G", "Person H", "Person I", "Person J",
]

COLOR_PALETTE = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990",
]

DEFAULT_FAMILIES = [
    ("Family A", ["Person A", "Person B"]),
    ("Family B", ["Person C", "Person D", "Person E", "Person F", "Person G"]),
    ("Family C", ["Person H", "Person I", "Person J"]),
]


def seed_people() -> None:
    """Seed default family members, colors, and families on first run."""
    inspector = inspect(db.engine)
    if not inspector.has_table("person"):
        return

    if Person.query.first() is not None:
        _backfill_colors()
        _backfill_families()
        return

    for i, name in enumerate(FAMILY_MEMBERS):
        db.session.add(Person(
            name=name,
            color=COLOR_PALETTE[i % len(COLOR_PALETTE)],
        ))
    db.session.commit()
    _seed_families()


def _backfill_colors() -> None:
    """Replace default blue with palette colors for existing people."""
    for i, person in enumerate(Person.query.order_by(Person.id).all()):
        if person.color == "#3388ff":
            person.color = COLOR_PALETTE[i % len(COLOR_PALETTE)]
    db.session.commit()


def _backfill_families() -> None:
    """Create families if none exist yet."""
    inspector = inspect(db.engine)
    if not inspector.has_table("family"):
        return
    if Family.query.first() is None:
        _seed_families()


def _seed_families() -> None:
    """Create default families and assign members."""
    for order, (fname, member_names) in enumerate(DEFAULT_FAMILIES):
        family = Family(name=fname, sort_order=order)
        db.session.add(family)
        db.session.flush()
        for mname in member_names:
            person = Person.query.filter_by(name=mname).first()
            if person:
                person.family_id = family.id
    db.session.commit()
