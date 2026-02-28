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

# Run database migrations
flask db upgrade

# Generate new migration after model changes
flask db migrate -m "description"

# Send daily email notifications (designed for cron)
flask send-notifications

# Production startup (Docker/Fly.io)
flask db upgrade && gunicorn -w 1 -b 0.0.0.0:8080 "app:create_app()"
```

No test suite exists. No npm/bundler — all frontend dependencies are loaded from CDN.

## Architecture

**Python/Flask app with Jinja2 templates, no frontend build step.**

- `app/__init__.py` — App factory (`create_app()`), initializes db/login/migrate, seeds default family members on first run
- `app/models.py` — SQLAlchemy models: `Family`, `Person`, `Trip`, `Config`, plus `trip_person` join table
- `app/auth.py` — Blueprint: `/login`, `/logout`. Single shared password via `APP_PASSWORD` env var
- `app/trips.py` — Blueprint: `/` (dashboard with map), `/trips` (list), `/trips/new`, `/trips/<id>/edit`, `/trips/<id>/delete`
- `app/admin.py` — Blueprint at `/admin`: CRUD for people and families
- `app/email.py` — Resend API email helpers for trip notifications
- `app/cli.py` — `flask send-notifications` CLI command for daily trip start/end emails
- `app/templates/` — Jinja2 templates using Pico CSS v2
- `app/static/style.css` — Custom styles and map styling
- `migrations/` — Alembic migration files managed by Flask-Migrate

## Key Design Decisions

- **Single-password auth**: One shared `FamilyUser` with id `"family"`, password from `APP_PASSWORD` env var
- **SQLite everywhere**: Local dev uses `app.db` in repo root; production uses `/data/app.db` on a Fly.io persistent volume
- **Overlapping trips**: When a person has overlapping trips on the same day, before noon ET shows the first trip, after noon ET shows the last trip
- **Map pins**: Custom SVG pin icons with per-person colors; co-located people get pixel-offset pins
- **Geocoding**: Client-side Nominatim (OpenStreetMap) via fetch in trip form
- **Seeding**: `_seed_people()` in `app/__init__.py` auto-seeds family members using raw SQL on first run

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | `"dev-secret-change-me"` | Flask session secret |
| `APP_PASSWORD` | `"family"` | Shared login password |
| `DATABASE_URL` | `sqlite:///app.db` | Database connection string |
| `RESEND_API_KEY` | (none) | Resend email API key |
| `RESEND_FROM_EMAIL` | `"Where Are Family A <notifications@updates.sheabrennan.com>"` | Sender address |
