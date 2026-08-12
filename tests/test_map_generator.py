"""Tests for map generator module."""

from pathlib import Path
from unittest.mock import patch

from app.map_generator import build_map_prompt, _prompt_hash


class TestBuildMapPrompt:
    def test_single_person_at_home(self):
        locations = [{"name": "Alice", "label": "Chicago",
                      "traveling": False, "travel_day": False}]
        prompt = build_map_prompt(locations)
        assert "Alice is in Chicago" in prompt
        assert "cartoon" in prompt.lower()
        assert "map" in prompt.lower()

    def test_multiple_people_same_location(self):
        locations = [
            {"name": "Alice", "label": "Chicago",
             "traveling": False, "travel_day": False},
            {"name": "Bob", "label": "Chicago",
             "traveling": False, "travel_day": False},
        ]
        prompt = build_map_prompt(locations)
        assert "Alice and Bob are in Chicago" in prompt

    def test_three_people_same_location(self):
        locations = [
            {"name": "A", "label": "Home", "traveling": False, "travel_day": False},
            {"name": "B", "label": "Home", "traveling": False, "travel_day": False},
            {"name": "C", "label": "Home", "traveling": False, "travel_day": False},
        ]
        prompt = build_map_prompt(locations)
        assert "A, B, and C are in Home" in prompt

    def test_travel_day_shows_transit(self):
        locations = [{"name": "Alice", "label": "Paris",
                      "traveling": True, "travel_day": True,
                      "from_label": "Chicago", "to_label": "Paris",
                      "transport_mode": "flying"}]
        prompt = build_map_prompt(locations)
        assert "Alice is traveling from Chicago to Paris by plane" in prompt

    def test_travel_day_driving(self):
        locations = [{"name": "Bob", "label": "Nashville",
                      "traveling": True, "travel_day": True,
                      "from_label": "Chicago", "to_label": "Nashville",
                      "transport_mode": "driving"}]
        prompt = build_map_prompt(locations)
        assert "Bob is traveling from Chicago to Nashville by car" in prompt

    def test_return_travel_day_swaps_from_to(self):
        # On a return day, from = trip destination, to = home, and "after" replaces "for"
        locations = [{"name": "Shea", "label": "McLean Visit",
                      "traveling": True, "travel_day": True,
                      "from_label": "McLean", "to_label": "Richmond",
                      "transport_mode": "driving", "is_return": True}]
        prompt = build_map_prompt(locations)
        assert "Shea is traveling from McLean to Richmond by car after a McLean Visit" in prompt

    def test_outbound_travel_day_uses_for(self):
        # On an outbound day, the trip title reads "for a {title}"
        locations = [{"name": "Shea", "label": "McLean Visit",
                      "traveling": True, "travel_day": True,
                      "from_label": "Richmond", "to_label": "McLean",
                      "transport_mode": "driving", "is_return": False}]
        prompt = build_map_prompt(locations)
        assert "Shea is traveling from Richmond to McLean by car for a McLean Visit" in prompt

    def test_non_travel_day_traveling(self):
        locations = [{"name": "Alice", "label": "Paris",
                      "traveling": True, "travel_day": False}]
        prompt = build_map_prompt(locations)
        assert "Alice is in Paris" in prompt


class TestPromptHash:
    def test_deterministic(self):
        assert _prompt_hash("test prompt") == _prompt_hash("test prompt")

    def test_different_prompts_differ(self):
        assert _prompt_hash("prompt A") != _prompt_hash("prompt B")

    def test_length(self):
        assert len(_prompt_hash("anything")) == 16


class TestGetOrGenerateMap:
    def test_cache_hit(self, app, tmp_path):
        from app.map_generator import get_or_generate_map
        img = tmp_path / "map_cache.png"
        hash_file = tmp_path / "map_cache.hash"
        locations = [{"name": "A", "label": "Home",
                      "traveling": False, "travel_day": False}]
        prompt = build_map_prompt(locations)
        expected_hash = _prompt_hash(prompt)
        img.write_bytes(b"\x89PNG")
        hash_file.write_text(expected_hash)
        with patch("app.map_generator._cache_paths", return_value=(img, hash_file)):
            result = get_or_generate_map(locations)
        assert result == img

    def test_cache_miss_generates(self, app, tmp_path):
        from app.map_generator import get_or_generate_map
        img = tmp_path / "map_cache.png"
        hash_file = tmp_path / "map_cache.hash"
        locations = [{"name": "A", "label": "Home",
                      "traveling": False, "travel_day": False}]
        ref = Path(app.root_path) / "static" / "family_reference.png"
        with patch("app.map_generator._cache_paths", return_value=(img, hash_file)), \
             patch("app.map_generator.generate_map_image", return_value=b"\x89PNG") as mock_gen:
            # Need reference image to exist
            if not ref.exists():
                ref.parent.mkdir(parents=True, exist_ok=True)
                ref.write_bytes(b"fake")
            result = get_or_generate_map(locations)
        assert result == img
        assert img.read_bytes() == b"\x89PNG"
        mock_gen.assert_called_once()

    def test_force_regenerates(self, app, tmp_path):
        from app.map_generator import get_or_generate_map
        img = tmp_path / "map_cache.png"
        hash_file = tmp_path / "map_cache.hash"
        locations = [{"name": "A", "label": "Home",
                      "traveling": False, "travel_day": False}]
        prompt = build_map_prompt(locations)
        img.write_bytes(b"old")
        hash_file.write_text(_prompt_hash(prompt))
        ref = Path(app.root_path) / "static" / "family_reference.png"
        with patch("app.map_generator._cache_paths", return_value=(img, hash_file)), \
             patch("app.map_generator.generate_map_image", return_value=b"new"):
            if not ref.exists():
                ref.parent.mkdir(parents=True, exist_ok=True)
                ref.write_bytes(b"fake")
            result = get_or_generate_map(locations, force=True)
        assert result == img
        assert img.read_bytes() == b"new"

    def test_no_reference_image(self, app, tmp_path):
        from app.map_generator import get_or_generate_map
        img = tmp_path / "map_cache.png"
        hash_file = tmp_path / "map_cache.hash"
        locations = [{"name": "A", "label": "Home",
                      "traveling": False, "travel_day": False}]
        with patch("app.map_generator._cache_paths", return_value=(img, hash_file)):
            # Neither reference path exists
            result = get_or_generate_map(locations)
        # Should return None since no image was generated or cached
        assert result is None

    def test_generation_failure_returns_existing_cache(self, app, tmp_path):
        from app.map_generator import get_or_generate_map
        img = tmp_path / "map_cache.png"
        hash_file = tmp_path / "map_cache.hash"
        img.write_bytes(b"old cached")
        hash_file.write_text("stale-hash")
        locations = [{"name": "A", "label": "Home",
                      "traveling": False, "travel_day": False}]
        ref = Path(app.root_path) / "static" / "family_reference.png"
        with patch("app.map_generator._cache_paths", return_value=(img, hash_file)), \
             patch("app.map_generator.generate_map_image", return_value=None):
            if not ref.exists():
                ref.parent.mkdir(parents=True, exist_ok=True)
                ref.write_bytes(b"fake")
            result = get_or_generate_map(locations)
        assert result == img
        assert img.read_bytes() == b"old cached"


class TestGenerateMapImage:
    def test_no_api_key(self, app):
        app.config["OPENAI_API_KEY"] = None
        from app.map_generator import generate_map_image
        result = generate_map_image("test prompt", "/fake/path.png")
        assert result is None


class TestEmailImage:
    """The compressed JPEG derivative served to email clients."""

    def _make_png(self, path, size=(1536, 1024)):
        from PIL import Image
        Image.new("RGB", size, (200, 120, 60)).save(path, "PNG")
        return path

    def test_downscales_and_compresses(self, app, tmp_path):
        from PIL import Image
        from app.map_generator import EMAIL_IMAGE_WIDTH, write_email_image
        img = self._make_png(tmp_path / "map_cache.png")
        with patch("app.map_generator._cache_paths",
                   return_value=(img, tmp_path / "map_cache.hash")):
            jpg = write_email_image()
        assert jpg is not None and jpg.suffix == ".jpg"
        with Image.open(jpg) as out:
            assert out.format == "JPEG"
            assert out.size == (EMAIL_IMAGE_WIDTH, 683)  # 3:2 preserved
        assert jpg.stat().st_size < img.stat().st_size

    def test_does_not_upscale_small_images(self, app, tmp_path):
        from PIL import Image
        from app.map_generator import write_email_image
        img = self._make_png(tmp_path / "map_cache.png", size=(400, 300))
        with patch("app.map_generator._cache_paths",
                   return_value=(img, tmp_path / "map_cache.hash")):
            jpg = write_email_image()
        with Image.open(jpg) as out:
            assert out.size == (400, 300)

    def test_returns_none_when_no_png(self, app, tmp_path):
        from app.map_generator import write_email_image
        with patch("app.map_generator._cache_paths",
                   return_value=(tmp_path / "missing.png", tmp_path / "h")):
            assert write_email_image() is None

    def test_handles_unreadable_png(self, app, tmp_path):
        from app.map_generator import write_email_image
        img = tmp_path / "map_cache.png"
        img.write_bytes(b"not actually a png")
        with patch("app.map_generator._cache_paths",
                   return_value=(img, tmp_path / "map_cache.hash")):
            assert write_email_image() is None

    def test_get_email_image_rederives_when_png_is_newer(self, app, tmp_path):
        import os
        from app.map_generator import _email_image_path, get_email_image
        img = self._make_png(tmp_path / "map_cache.png")
        with patch("app.map_generator._cache_paths",
                   return_value=(img, tmp_path / "map_cache.hash")):
            first = get_email_image()
            stale = b"stale jpeg bytes"
            first.write_bytes(stale)
            # Mark the JPEG as older than the PNG
            png_mtime = img.stat().st_mtime
            os.utime(first, (png_mtime - 60, png_mtime - 60))
            second = get_email_image()
            assert second == _email_image_path()
            assert second.read_bytes() != stale

    def test_get_email_image_reuses_current_derivative(self, app, tmp_path):
        from app.map_generator import get_email_image
        img = self._make_png(tmp_path / "map_cache.png")
        with patch("app.map_generator._cache_paths",
                   return_value=(img, tmp_path / "map_cache.hash")):
            first = get_email_image()
            marker = first.stat().st_mtime_ns
            again = get_email_image()
        assert again.stat().st_mtime_ns == marker


class TestMapTokenAndVersion:
    def test_token_is_stable_and_secret_derived(self, app, tmp_path):
        from app.map_generator import map_token
        first = map_token()
        assert first == map_token()
        assert len(first) == 16
        app.config["SECRET_KEY"] = "a-different-secret"
        assert map_token() != first

    def test_version_none_without_image(self, app, tmp_path):
        from app.map_generator import map_version
        with patch("app.map_generator._cache_paths",
                   return_value=(tmp_path / "missing.png", tmp_path / "h")):
            assert map_version() is None

    def test_version_uses_hash_file(self, app, tmp_path):
        from app.map_generator import map_version
        img = tmp_path / "map_cache.png"
        img.write_bytes(b"\x89PNG")
        hash_file = tmp_path / "map_cache.hash"
        hash_file.write_text("cafebabe12345678\n")
        with patch("app.map_generator._cache_paths", return_value=(img, hash_file)):
            assert map_version() == "cafebabe12345678"
