from pathlib import Path
from unittest.mock import patch, MagicMock

from freezegun import freeze_time

from app.map_generator import build_map_prompt, _prompt_hash, get_or_generate_map


class TestBuildMapPrompt:
    def test_single_person_stationary(self):
        locations = [
            {"name": "Alice", "label": "Nashville, TN", "traveling": False,
             "travel_day": False, "home_label": "Nashville, TN"},
        ]
        prompt = build_map_prompt(locations)
        assert "Alice is in Nashville, TN" in prompt

    def test_multiple_people_same_location(self):
        locations = [
            {"name": "Person H", "label": "Nashville, TN", "traveling": False,
             "travel_day": False, "home_label": "Nashville, TN"},
            {"name": "Person I", "label": "Nashville, TN", "traveling": False,
             "travel_day": False, "home_label": "Nashville, TN"},
        ]
        prompt = build_map_prompt(locations)
        assert "Gordon and Renee are in Nashville, TN" in prompt

    def test_three_people_same_location(self):
        locations = [
            {"name": "A", "label": "NYC", "traveling": False,
             "travel_day": False, "home_label": "NYC"},
            {"name": "B", "label": "NYC", "traveling": False,
             "travel_day": False, "home_label": "NYC"},
            {"name": "C", "label": "NYC", "traveling": False,
             "travel_day": False, "home_label": "NYC"},
        ]
        prompt = build_map_prompt(locations)
        assert "A, B, and C are in NYC" in prompt

    def test_flying_travel_day(self):
        locations = [
            {"name": "Person B", "label": "Montego Bay, Jamaica", "traveling": True,
             "travel_day": True, "home_label": "Richmond, VA",
             "transport_mode": "flying"},
        ]
        prompt = build_map_prompt(locations)
        assert "Alex is flying from Richmond, VA to Montego Bay, Jamaica" in prompt

    def test_driving_travel_day(self):
        locations = [
            {"name": "Person C", "label": "Nashville, TN", "traveling": True,
             "travel_day": True, "home_label": "Richmond, VA",
             "transport_mode": "driving"},
        ]
        prompt = build_map_prompt(locations)
        assert "Shea is driving from Richmond, VA to Nashville, TN" in prompt

    def test_train_travel_day(self):
        locations = [
            {"name": "Person D", "label": "DC", "traveling": True,
             "travel_day": True, "home_label": "Richmond, VA",
             "transport_mode": "train"},
        ]
        prompt = build_map_prompt(locations)
        assert "Mary is taking a train from Richmond, VA to DC" in prompt

    def test_boat_travel_day(self):
        locations = [
            {"name": "Person H", "label": "Bermuda", "traveling": True,
             "travel_day": True, "home_label": "Richmond, VA",
             "transport_mode": "boat"},
        ]
        prompt = build_map_prompt(locations)
        assert "Gordon is taking a boat from Richmond, VA to Bermuda" in prompt

    def test_multiple_people_flying(self):
        locations = [
            {"name": "Person B", "label": "Jamaica", "traveling": True,
             "travel_day": True, "home_label": "Richmond, VA",
             "transport_mode": "flying"},
            {"name": "Person A", "label": "Jamaica", "traveling": True,
             "travel_day": True, "home_label": "Richmond, VA",
             "transport_mode": "flying"},
        ]
        prompt = build_map_prompt(locations)
        assert "Alex and Mimsy are flying from Richmond, VA to Jamaica" in prompt

    def test_prompt_includes_system_instruction(self):
        locations = [
            {"name": "Test", "label": "Home", "traveling": False,
             "travel_day": False, "home_label": "Home"},
        ]
        prompt = build_map_prompt(locations)
        assert "Conaway Family" in prompt
        assert "cartoon map" in prompt
        assert "reference photo" in prompt

    def test_mixed_locations(self):
        locations = [
            {"name": "Alice", "label": "Nashville, TN", "traveling": False,
             "travel_day": False, "home_label": "Nashville, TN"},
            {"name": "Bob", "label": "Tokyo", "traveling": True,
             "travel_day": False, "home_label": "Nashville, TN"},
        ]
        prompt = build_map_prompt(locations)
        assert "Alice is in Nashville, TN" in prompt
        assert "Bob is in Tokyo" in prompt


class TestPromptHash:
    def test_deterministic(self):
        h1 = _prompt_hash("test prompt")
        h2 = _prompt_hash("test prompt")
        assert h1 == h2

    def test_different_prompts_different_hashes(self):
        h1 = _prompt_hash("prompt one")
        h2 = _prompt_hash("prompt two")
        assert h1 != h2

    def test_returns_string(self):
        h = _prompt_hash("test")
        assert isinstance(h, str)
        assert len(h) == 16


class TestGetOrGenerateMap:
    def test_skips_when_hash_matches(self, app, tmp_path):
        with patch("app.map_generator._cache_dir", return_value=tmp_path):
            with patch("app.map_generator._cache_paths") as mock_paths:
                image_path = tmp_path / "map_cache.png"
                hash_path = tmp_path / "map_cache.hash"
                mock_paths.return_value = (image_path, hash_path)

                locations = [
                    {"name": "Test", "label": "Home", "traveling": False,
                     "travel_day": False, "home_label": "Home"},
                ]
                prompt = build_map_prompt(locations)
                current_hash = _prompt_hash(prompt)

                # Pre-populate cache
                image_path.write_bytes(b"fake png")
                hash_path.write_text(current_hash)

                with patch("app.map_generator.generate_map_image") as mock_gen:
                    result = get_or_generate_map(locations)
                    mock_gen.assert_not_called()
                    assert result == image_path

    def test_regenerates_when_hash_differs(self, app, tmp_path):
        with patch("app.map_generator._cache_dir", return_value=tmp_path):
            with patch("app.map_generator._cache_paths") as mock_paths:
                image_path = tmp_path / "map_cache.png"
                hash_path = tmp_path / "map_cache.hash"
                mock_paths.return_value = (image_path, hash_path)

                # Stale hash
                image_path.write_bytes(b"old png")
                hash_path.write_text("stale_hash")

                # Create a dummy reference image
                ref_path = Path(app.root_path) / "static" / "family_reference.png"
                ref_path.parent.mkdir(parents=True, exist_ok=True)
                ref_path.write_bytes(b"fake ref")

                locations = [
                    {"name": "Test", "label": "Home", "traveling": False,
                     "travel_day": False, "home_label": "Home"},
                ]

                with patch("app.map_generator.generate_map_image", return_value=b"new png") as mock_gen:
                    result = get_or_generate_map(locations)
                    mock_gen.assert_called_once()
                    assert result == image_path
                    assert image_path.read_bytes() == b"new png"

    def test_force_regenerates(self, app, tmp_path):
        with patch("app.map_generator._cache_dir", return_value=tmp_path):
            with patch("app.map_generator._cache_paths") as mock_paths:
                image_path = tmp_path / "map_cache.png"
                hash_path = tmp_path / "map_cache.hash"
                mock_paths.return_value = (image_path, hash_path)

                locations = [
                    {"name": "Test", "label": "Home", "traveling": False,
                     "travel_day": False, "home_label": "Home"},
                ]
                prompt = build_map_prompt(locations)
                current_hash = _prompt_hash(prompt)

                # Cache is current
                image_path.write_bytes(b"old png")
                hash_path.write_text(current_hash)

                ref_path = Path(app.root_path) / "static" / "family_reference.png"
                ref_path.parent.mkdir(parents=True, exist_ok=True)
                ref_path.write_bytes(b"fake ref")

                with patch("app.map_generator.generate_map_image", return_value=b"forced png") as mock_gen:
                    result = get_or_generate_map(locations, force=True)
                    mock_gen.assert_called_once()
                    assert image_path.read_bytes() == b"forced png"

    def test_returns_none_when_no_cache_and_generation_fails(self, app, tmp_path):
        with patch("app.map_generator._cache_dir", return_value=tmp_path):
            with patch("app.map_generator._cache_paths") as mock_paths:
                image_path = tmp_path / "map_cache.png"
                hash_path = tmp_path / "map_cache.hash"
                mock_paths.return_value = (image_path, hash_path)

                ref_path = Path(app.root_path) / "static" / "family_reference.png"
                ref_path.parent.mkdir(parents=True, exist_ok=True)
                ref_path.write_bytes(b"fake ref")

                locations = [
                    {"name": "Test", "label": "Home", "traveling": False,
                     "travel_day": False, "home_label": "Home"},
                ]

                with patch("app.map_generator.generate_map_image", return_value=None):
                    result = get_or_generate_map(locations)
                    assert result is None


class TestMapImageRoute:
    def test_returns_404_without_cached_image(self, auth_client, app, tmp_path):
        with patch("app.map_generator._cache_paths") as mock_paths:
            mock_paths.return_value = (tmp_path / "nonexistent.png", tmp_path / "nonexistent.hash")
            resp = auth_client.get("/map-image")
            assert resp.status_code == 404

    def test_returns_200_with_cached_image(self, auth_client, app, tmp_path):
        image_path = tmp_path / "map_cache.png"
        image_path.write_bytes(b"\x89PNG fake image data")
        with patch("app.map_generator._cache_paths") as mock_paths:
            mock_paths.return_value = (image_path, tmp_path / "map_cache.hash")
            resp = auth_client.get("/map-image")
            assert resp.status_code == 200
            assert resp.content_type == "image/png"

    def test_requires_login(self, client):
        resp = client.get("/map-image")
        assert resp.status_code == 302
