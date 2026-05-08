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
