import hashlib
import hmac
import logging
from pathlib import Path

from flask import current_app

logger = logging.getLogger(__name__)

EMAIL_IMAGE_WIDTH = 1024
EMAIL_IMAGE_QUALITY = 70


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
            trip_title = label if label != to_label else None
            if trip_title:
                purpose_word = "after" if members[0].get("is_return") else "for"
                trip_note = f" {purpose_word} a {trip_title}"
            else:
                trip_note = ""
            verb = "are" if len(members) > 1 else "is"
            sentences.append(
                f"{names} {verb} traveling from {from_label} to {to_label}{mode_suffix}{trip_note}."
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
        f"matching the labeled reference photo. "
        f"Double-check the geographic accuracy of all city and location placements. "
        f"Make sure each city is positioned correctly relative to other cities and landmarks."
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


def _email_image_path() -> Path:
    """Return the path of the compressed JPEG served to email clients."""
    png_path, _ = _cache_paths()
    return png_path.with_name("map_cache_email.jpg")


def map_token() -> str:
    """Return the stable, unguessable path token for the public map URL.

    Derived from SECRET_KEY rather than the map contents so that previously
    sent emails keep resolving after the map regenerates.
    """
    secret = current_app.config["SECRET_KEY"].encode()
    return hmac.new(secret, b"map-image", hashlib.sha256).hexdigest()[:16]


def map_version() -> str | None:
    """Return a short content version for cache-busting, or None if no map."""
    image_path, hash_path = _cache_paths()
    if not image_path.exists():
        return None
    if hash_path.exists():
        return hash_path.read_text().strip()
    # Caches written before the hash file existed
    return hashlib.sha256(image_path.read_bytes()).hexdigest()[:16]


def write_email_image() -> Path | None:
    """Derive the compressed JPEG used in emails from the cached PNG."""
    png_path, _ = _cache_paths()
    if not png_path.exists():
        return None
    jpg_path = _email_image_path()
    try:
        from PIL import Image

        with Image.open(png_path) as im:
            im = im.convert("RGB")  # JPEG has no alpha channel
            width, height = im.size
            if width > EMAIL_IMAGE_WIDTH:
                new_height = round(height * EMAIL_IMAGE_WIDTH / width)
                im = im.resize((EMAIL_IMAGE_WIDTH, new_height), Image.LANCZOS)
            im.save(
                jpg_path,
                "JPEG",
                quality=EMAIL_IMAGE_QUALITY,
                optimize=True,
                progressive=True,
            )
        return jpg_path
    except Exception:
        logger.exception("Failed to derive email JPEG from %s", png_path)
        return None


def get_email_image() -> Path | None:
    """Return the email JPEG, deriving it if missing or older than the PNG."""
    png_path, _ = _cache_paths()
    if not png_path.exists():
        return None
    jpg_path = _email_image_path()
    if jpg_path.exists() and jpg_path.stat().st_mtime >= png_path.stat().st_mtime:
        return jpg_path
    return write_email_image()


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
        write_email_image()
        logger.info("Map image generated and cached at %s", image_path)
        return image_path

    logger.warning("Map generation failed, using existing cache if available")
    return image_path if image_path.exists() else None
