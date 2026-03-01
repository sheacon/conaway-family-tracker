# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Family travel tracker — a Flask web app where family members enter travel plans, view current locations on an interactive Leaflet map, and see upcoming trips. Single shared password auth (Flask-Login). Deployed on Fly.io with SQLite.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run dev server
flask --app app:create_app run

# Run tests
pytest

# Run database migrations
flask db upgrade

# Generate new migration after model changes
flask db migrate -m "description"

# Send daily email notifications (runs locally for testing)
flask send-notifications

# Production startup (Docker/Fly.io)
flask db upgrade && gunicorn -w 1 -b 0.0.0.0:8080 "app:create_app()"
```

## Architecture

**Python/Flask app with Jinja2 templates, no frontend build step.**

- `app/__init__.py` — App factory (`create_app()`), initializes db/login/migrate, registers blueprints and filters
- `app/models.py` — SQLAlchemy models: `Family`, `Person`, `Trip`, `TripStop`, `Config`, plus `trip_person` join table
- `app/auth.py` — Blueprint: `/login`, `/logout`. Single shared password via `APP_PASSWORD` env var
- `app/trips.py` — Blueprint: `/` (dashboard with map), `/trips` (list), `/trips/new`, `/trips/<id>/edit`, `/trips/<id>/delete`
- `app/admin.py` — Blueprint at `/admin`: CRUD for people and families, notification toggle
- `app/email.py` — Resend API email helpers for trip notifications
- `app/cli.py` — `flask send-notifications` CLI command for trip start/end emails (scheduled via GitHub Actions)
- `app/filters.py` — Jinja2 template filters: `flight_link` (FlightAware URLs), `group_by_family`
- `app/seed.py` — Seeds default family members and families on first run
- `app/templates/` — Jinja2 templates using Pico CSS v2
- `app/static/style.css` — Custom styles and map styling
- `config.py` — Flask configuration from environment variables
- `migrations/` — Alembic migration files managed by Flask-Migrate
- `tests/` — pytest test suite with freezegun for time-dependent tests

## Key Design Decisions

- **Single-password auth**: One shared `FamilyUser` with id `"family"`, password from `APP_PASSWORD` env var
- **SQLite everywhere**: Local dev uses `app.db` in repo root; production uses `/data/app.db` on a Fly.io persistent volume
- **Multi-stop trips**: Trips have ordered `TripStop` records. Denormalized fields on `Trip` (`destination`, `latitude`, `longitude`, `start_date`, `end_date`) are synced from stops via `sync_from_stops()`
- **Overlapping trips**: When a person has overlapping trips on the same day, before noon ET shows the first trip, after noon ET shows the last trip
- **Map pins**: Custom SVG pin icons with per-person colors; co-located people get pixel-offset pins
- **Geocoding**: Client-side Nominatim (OpenStreetMap) via fetch in trip form
- **Seeding**: `seed_people()` in `app/seed.py` auto-seeds family members on first run; checks for table existence to survive pre-migration state
- **Scheduled notifications**: GitHub Actions workflow (`.github/workflows/daily-notifications.yml`) runs `flask send-notifications` daily at 8 AM ET. It wakes the Fly.io machine via HTTP (since `auto_stop_machines` is enabled), then SSHes in to run the command. Requires an org-scoped `FLY_API_TOKEN` GitHub secret (deploy tokens lack SSH access)

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | `"dev-secret-change-me"` | Flask session secret |
| `APP_PASSWORD` | `"family"` | Shared login password |
| `DATABASE_URL` | `sqlite:///app.db` | Database connection string |
| `RESEND_API_KEY` | (none) | Resend email API key |
| `RESEND_FROM_EMAIL` | (none) | Sender address |
