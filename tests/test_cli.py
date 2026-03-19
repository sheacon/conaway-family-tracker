"""Tests for CLI commands."""

from datetime import date
from unittest.mock import patch

from freezegun import freeze_time


class TestSendNotifications:
    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_starting_soon(self, app, make_trip, make_person):
        make_person(name="A", email="a@example.com")
        make_trip(destination="Paris",
                  start_date=date(2026, 6, 4), end_date=date(2026, 6, 10))
        runner = app.test_cli_runner()
        with patch("app.cli.notify_trip_starting_soon") as mock:
            result = runner.invoke(args=["send-notifications"])
        assert result.exit_code == 0
        mock.assert_called_once()
        assert "Starting soon" in result.output

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_started_today(self, app, make_trip, make_person):
        make_person(name="A", email="a@example.com")
        make_trip(destination="Paris",
                  start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        runner = app.test_cli_runner()
        with patch("app.cli.notify_trip_started") as mock:
            result = runner.invoke(args=["send-notifications"])
        assert result.exit_code == 0
        mock.assert_called_once()
        assert "Starting today" in result.output

    @freeze_time("2026-06-05 12:00:00", tz_offset=0)
    def test_ended_today(self, app, make_trip, make_person):
        make_person(name="A", email="a@example.com")
        make_trip(destination="Paris",
                  start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        runner = app.test_cli_runner()
        with patch("app.cli.notify_trip_ended") as mock:
            result = runner.invoke(args=["send-notifications"])
        assert result.exit_code == 0
        mock.assert_called_once()
        assert "Ending today" in result.output

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_same_day_trip_excluded_from_ending(self, app, make_trip):
        make_trip(destination="DayTrip",
                  start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))
        runner = app.test_cli_runner()
        with patch("app.cli.notify_trip_ended") as mock:
            result = runner.invoke(args=["send-notifications"])
        assert result.exit_code == 0
        mock.assert_not_called()

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_no_matching_trips(self, app):
        runner = app.test_cli_runner()
        with patch("app.cli.notify_trip_starting_soon") as mock_soon, \
             patch("app.cli.notify_trip_started") as mock_start, \
             patch("app.cli.notify_trip_ended") as mock_end:
            result = runner.invoke(args=["send-notifications"])
        assert result.exit_code == 0
        mock_soon.assert_not_called()
        mock_start.assert_not_called()
        mock_end.assert_not_called()
        assert "Done." in result.output

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_uses_display_name_in_output(self, app, make_trip):
        make_trip(destination="Paris", title="Spring Break",
                  start_date=date(2026, 6, 1), end_date=date(2026, 6, 5))
        runner = app.test_cli_runner()
        with patch("app.cli.notify_trip_started"):
            result = runner.invoke(args=["send-notifications"])
        assert "Spring Break" in result.output

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_all_notification_types_at_once(self, app, make_trip):
        # Trip starting in 3 days
        make_trip(destination="Soon",
                  start_date=date(2026, 6, 4), end_date=date(2026, 6, 8))
        # Trip starting today
        make_trip(destination="Today",
                  start_date=date(2026, 6, 1), end_date=date(2026, 6, 3))
        # Trip ending today (started before)
        make_trip(destination="Ending",
                  start_date=date(2026, 5, 28), end_date=date(2026, 6, 1))
        runner = app.test_cli_runner()
        with patch("app.cli.notify_trip_starting_soon") as m1, \
             patch("app.cli.notify_trip_started") as m2, \
             patch("app.cli.notify_trip_ended") as m3:
            result = runner.invoke(args=["send-notifications"])
        assert result.exit_code == 0
        m1.assert_called_once()
        m2.assert_called_once()
        m3.assert_called_once()


class TestGenerateMap:
    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_generates_map(self, app, tmp_path):
        runner = app.test_cli_runner()
        img = tmp_path / "map.png"
        with patch("app.cli.get_or_generate_map", return_value=img):
            result = runner.invoke(args=["generate-map"])
        assert result.exit_code == 0
        assert str(img) in result.output

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_no_map_generated(self, app):
        runner = app.test_cli_runner()
        with patch("app.cli.get_or_generate_map", return_value=None):
            result = runner.invoke(args=["generate-map"])
        assert result.exit_code == 0
        assert "No map image generated" in result.output

    @freeze_time("2026-06-01 12:00:00", tz_offset=0)
    def test_force_flag(self, app, tmp_path):
        runner = app.test_cli_runner()
        img = tmp_path / "map.png"
        with patch("app.cli.get_or_generate_map", return_value=img) as mock:
            result = runner.invoke(args=["generate-map", "--force"])
        assert result.exit_code == 0
        mock.assert_called_once()
        _, kwargs = mock.call_args
        assert kwargs["force"] is True
