import json
import logging
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError

from app import db
from app.models import Family, Person

logger = logging.getLogger(__name__)

_SEED_DATA_PATH = Path(__file__).resolve().parent.parent / "seed_data.json"


def _load_seed_data() -> dict | None:
    """Load seed data from JSON file, returning None if unavailable."""
    if not _SEED_DATA_PATH.exists():
        logger.warning(
            "Seed data file not found at %s — skipping seeding. "
            "Copy seed_data.example.json to seed_data.json to configure.",
            _SEED_DATA_PATH,
        )
        return None
    try:
        return json.loads(_SEED_DATA_PATH.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read seed data from %s: %s", _SEED_DATA_PATH, exc)
        return None


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

    data = _load_seed_data()
    if data is None:
        return

    for name in data.get("people", []):
        db.session.add(Person(name=name))
    db.session.commit()
    _seed_families(data)


def _backfill_families() -> None:
    """Create families if none exist yet."""
    inspector = inspect(db.engine)
    if not inspector.has_table("family"):
        return
    if Family.query.first() is None:
        data = _load_seed_data()
        if data is not None:
            _seed_families(data)


def _seed_families(data: dict) -> None:
    """Create default families and assign members."""
    for order, family_def in enumerate(data.get("families", [])):
        family = Family(name=family_def["name"], sort_order=order)
        db.session.add(family)
        db.session.flush()
        for mname in family_def.get("members", []):
            person = Person.query.filter_by(name=mname).first()
            if person:
                person.family_id = family.id
    db.session.commit()
