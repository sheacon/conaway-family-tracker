from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError

from app import db
from app.models import Family, Person

FAMILY_MEMBERS = [
    "Person A", "Person B", "Person C", "Person D", "Person E",
    "Person F", "Person G", "Person H", "Person I", "Person J",
]

DEFAULT_FAMILIES = [
    ("Family A", ["Person A", "Person B"]),
    ("Family B", ["Person C", "Person D", "Person E", "Person F", "Person G"]),
    ("Family C", ["Person H", "Person I", "Person J"]),
]


def seed_people() -> None:
    """Seed default family members and families on first run."""
    inspector = inspect(db.engine)
    if not inspector.has_table("person"):
        return

    try:
        existing = Person.query.first()
    except OperationalError:
        return
    if existing is not None:
        _backfill_families()
        return

    for name in FAMILY_MEMBERS:
        db.session.add(Person(name=name))
    db.session.commit()
    _seed_families()


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
