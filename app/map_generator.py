import hashlib
import logging
from pathlib import Path

from flask import current_app

logger = logging.getLogger(__name__)


def build_map_prompt(locations: list[dict]) -> str:
    """Build a text prompt describing everyone's current location."""
    # Group people by location label and travel status
    groups: dict[str, list[dict]] = {}
    for loc in locations:
        key = (loc["label"], loc.get("travel_day", False))
        groups.setdefault(key, []).append(loc)

    sentences = []
    for (label, travel_day), members in groups.items():
        names = " and ".join(m["name"] for m in members) if len(members) <= 2 else (
            ", ".join(m["name"] for m in members[:-1]) + ", and " + members[-1]["name"]
        )

        if travel_day and members[0].get("traveling"):
            from_label = members[0].get("from_label", "Home")
            mode = members[0].get("transport_mode", "flying")
            mode_word = {
                "flying": "plane",
                "driving": "car",
                "train": "train",
                "boat": "boat",
            }.get(mode)
            mode_suffix = f" by {mode_word}" if mode_word else ""
            to_label = members[0].get("to_label") or label
            verb = "are" if len(members) > 1 else "is"
            sentences.append(
                f"{names} {verb} traveling from {from_label} to {to_label}{mode_suffix}."
            )
        else:
            sentences.append(
                f"{names} are in {label}."
                if len(members) > 1 else
                f"{names} is in {label}."
            )

    location_text = " ".join(sentences)
    prompt = (
        f"Create a cartoon illustrated map titled 'Conaway Family Map'. "
        f"{location_text} "
        f"Place cartoon versions of each person at their location, "
        f"matching the labeled reference photo."
    )
    return prompt


def _prompt_hash(prompt: str) -> str:
    """Return a short SHA-256 hex digest of the prompt."""
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


def _cache_dir() -> Path:
    """Return the cache directory for map images."""
    db_url = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if "/data/" in db_url:
        cache = Path("/data")
    else:
        cache = Path(current_app.root_path).parent
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def _cache_paths() -> tuple[Path, Path]:
    """Return (image_path, hash_path) for the cached map."""
    cache = _cache_dir()
    return cache / "map_cache.png", cache / "map_cache.hash"


def generate_map_image(prompt: str, reference_image_path: str) -> bytes | None:
    """Call the OpenAI API to generate a cartoon map image.

    Returns image bytes on success, None on failure.
    """
    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not configured")
        return None

    try:
        import base64
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        with open(reference_image_path, "rb") as ref:
            result = client.images.edit(
                model="gpt-image-2",
                image=ref,
                prompt=prompt,
                size="1536x1024",
                quality="high",
                output_format="png",
            )

        return base64.b64decode(result.data[0].b64_json)

    except Exception:
        logger.exception("Failed to generate map image via OpenAI API")
        return None


def get_or_generate_map(locations: list[dict], force: bool = False) -> Path | None:
    """Get the cached map image, regenerating if locations have changed.

    Returns path to the cached image, or None if no image exists.
    """
    prompt = build_map_prompt(locations)
    current_hash = _prompt_hash(prompt)
    image_path, hash_path = _cache_paths()

    # Check if cached hash matches
    if not force and hash_path.exists() and image_path.exists():
        cached_hash = hash_path.read_text().strip()
        if cached_hash == current_hash:
            logger.info("Map cache is current, skipping regeneration")
            return image_path

    # Generate new image — reference photo lives on persistent volume in prod
    reference_path = Path("/data/family_reference.png")
    if not reference_path.exists():
        reference_path = Path(current_app.root_path) / "static" / "family_reference.png"
    if not reference_path.exists():
        logger.error("Family reference image not found at %s", reference_path)
        return image_path if image_path.exists() else None

    image_bytes = generate_map_image(prompt, str(reference_path))
    if image_bytes:
        image_path.write_bytes(image_bytes)
        hash_path.write_text(current_hash)
        logger.info("Map image generated and cached at %s", image_path)
        return image_path

    logger.warning("Map generation failed, using existing cache if available")
    return image_path if image_path.exists() else None
