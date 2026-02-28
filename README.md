# Conaway Family Tracker

A Flask web app for tracking family travel plans. Members enter upcoming trips, view everyone's current location on an interactive Leaflet map, and browse upcoming travel. Daily email notifications alert the family when trips start or end.

## Features

- **Interactive map** — Dashboard shows each person's current location with color-coded SVG pin icons
- **Trip management** — Create, edit, and delete trips with destination, dates, and travellers
- **Geocoding** — Client-side geocoding via OpenStreetMap Nominatim
- **Email notifications** — Daily start/end alerts sent via the Resend API
- **Admin panel** — Manage people and families
- **Single shared password** — Simple auth via Flask-Login (one password for the whole family)

## Tech Stack

- **Backend:** Python / Flask, SQLAlchemy, Flask-Migrate (Alembic)
- **Frontend:** Jinja2 templates, Pico CSS v2, Leaflet.js (all from CDN — no build step)
- **Database:** SQLite
- **Deployment:** Docker on Fly.io with a persistent volume
- **Email:** Resend API
- **Scheduled jobs:** GitHub Actions cron workflow

## Local Development

```bash
# Create a virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run database migrations
flask db upgrade

# Start the dev server
flask --app app:create_app run
```

### Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | `"dev-secret-change-me"` | Flask session secret |
| `APP_PASSWORD` | `"family"` | Shared login password |
| `DATABASE_URL` | `sqlite:///app.db` | Database connection string |
| `RESEND_API_KEY` | *(none)* | Resend email API key |
| `RESEND_FROM_EMAIL` | `"Where Are Family A <notifications@updates.sheabrennan.com>"` | Sender address |

## Project Structure

```
app/
  __init__.py      # App factory, DB init, family member seeding
  models.py        # SQLAlchemy models (Family, Person, Trip, Config)
  auth.py          # /login, /logout blueprint
  trips.py         # Dashboard, trip CRUD blueprint
  admin.py         # /admin people & family management
  email.py         # Resend API email helpers
  cli.py           # flask send-notifications CLI command
  templates/       # Jinja2 templates (Pico CSS v2)
  static/style.css # Custom styles and map styling
migrations/        # Alembic migrations (Flask-Migrate)
Dockerfile         # Python 3.14-slim container
fly.toml           # Fly.io deployment config
```

## Deployment

The app runs on Fly.io (`ord` region) with a persistent SQLite volume mounted at `/data`. Auto-stop is enabled to save resources — the machine starts on demand when a request arrives.

```bash
fly deploy
```

### Scheduled Notifications

A GitHub Actions workflow (`.github/workflows/daily-notifications.yml`) runs daily at 8 AM ET. It wakes the Fly.io machine via HTTP, then SSHes in to run `flask send-notifications`. Requires an org-scoped `FLY_API_TOKEN` GitHub secret.
