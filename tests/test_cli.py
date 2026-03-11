from datetime import date
from unittest.mock import patch

from freezegun import freeze_time


class TestSendNotifications:
    @freeze_time("2026-03-01 12:00:00")
    @patch("app.cli.notify_trip_starting_soon")
    def test_trip_starting_in_3_days(self, mock_notify, app, make_trip):
        make_trip(
            destination="Soon", start_date=date(2026, 3, 4), end_date=date(2026, 3, 8)
        )
        runner = app.test_cli_runner()
        result = runner.invoke(args=["send-notifications"])
        mock_notify.assert_called_once()
        assert "Starting soon: Soon" in result.output

    @freeze_time("2026-03-01 12:00:00")
    @patch("app.cli.notify_trip_started")
    def test_trip_starting_today(self, mock_notify, app, make_trip):
        make_trip(
            destination="Today", start_date=date(2026, 3, 1), end_date=date(2026, 3, 5)
        )
        runner = app.test_cli_runner()
        result = runner.invoke(args=["send-notifications"])
        mock_notify.assert_called_once()
        assert "Starting today: Today" in result.output

    @freeze_time("2026-03-05 12:00:00")
    @patch("app.cli.notify_trip_ended")
    def test_trip_ending_today(self, mock_notify, app, make_trip):
        make_trip(
            destination="Ending", start_date=date(2026, 3, 1), end_date=date(2026, 3, 5)
        )
        runner = app.test_cli_runner()
        result = runner.invoke(args=["send-notifications"])
        mock_notify.assert_called_once()
        assert "Ending today: Ending" in result.output

    @freeze_time("2026-03-01 12:00:00")
    @patch("app.cli.notify_trip_ended")
    @patch("app.cli.notify_trip_started")
    def test_same_day_trip_not_ended(self, mock_started, mock_ended, app, make_trip):
        make_trip(
            destination="DayTrip",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 1),
        )
        runner = app.test_cli_runner()
        runner.invoke(args=["send-notifications"])
        mock_started.assert_called_once()
        mock_ended.assert_not_called()

    @freeze_time("2026-03-10 12:00:00")
    @patch("app.cli.notify_trip_starting_soon")
    @patch("app.cli.notify_trip_started")
    @patch("app.cli.notify_trip_ended")
    def test_no_matching_trips(self, mock_ended, mock_started, mock_soon, app):
        runner = app.test_cli_runner()
        result = runner.invoke(args=["send-notifications"])
        mock_soon.assert_not_called()
        mock_started.assert_not_called()
        mock_ended.assert_not_called()
        assert "Done." in result.output

    @freeze_time("2026-03-01 12:00:00")
    @patch("app.cli.notify_trip_starting_soon")
    def test_2_days_out_ignored(self, mock_notify, app, make_trip):
        make_trip(
            destination="TwoDays",
            start_date=date(2026, 3, 3),
            end_date=date(2026, 3, 6),
        )
        runner = app.test_cli_runner()
        runner.invoke(args=["send-notifications"])
        mock_notify.assert_not_called()

    @freeze_time("2026-03-01 12:00:00")
    @patch("app.cli.notify_trip_starting_soon")
    def test_4_days_out_ignored(self, mock_notify, app, make_trip):
        make_trip(
            destination="FourDays",
            start_date=date(2026, 3, 5),
            end_date=date(2026, 3, 8),
        )
        runner = app.test_cli_runner()
        runner.invoke(args=["send-notifications"])
        mock_notify.assert_not_called()

    @freeze_time("2026-03-05 12:00:00")
    @patch("app.cli.notify_trip_ended")
    @patch("app.cli.notify_trip_started")
    @patch("app.cli.notify_trip_starting_soon")
    def test_multiple_matching_trips(
        self, mock_soon, mock_started, mock_ended, app, make_trip
    ):
        make_trip(
            destination="SoonTrip",
            start_date=date(2026, 3, 8),
            end_date=date(2026, 3, 12),
        )
        make_trip(
            destination="TodayTrip",
            start_date=date(2026, 3, 5),
            end_date=date(2026, 3, 9),
        )
        make_trip(
            destination="EndTrip",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 5),
        )
        runner = app.test_cli_runner()
        runner.invoke(args=["send-notifications"])
        mock_soon.assert_called_once()
        mock_started.assert_called_once()
        mock_ended.assert_called_once()

    @freeze_time("2026-03-10 12:00:00")
    def test_output_done(self, app):
        runner = app.test_cli_runner()
        result = runner.invoke(args=["send-notifications"])
        assert "Done." in result.output
