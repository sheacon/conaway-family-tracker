# Conaway Family Tracker

A Flask web app for tracking family travel plans. Members enter upcoming trips, view everyone's current location on an interactive Leaflet map, and browse upcoming travel. Daily email notifications alert the family when trips start or end.

## Features

- **Interactive map** — Dashboard shows each person's current location with color-coded SVG pin icons
- **Multi-stop trips** — Plan trips with multiple destinations connected by a route
- **Trip management** — Create, edit, and delete trips with destination, dates, and travellers
- **Flight tracking** — Enter flight numbers with auto-links to FlightAware (IATA→ICAO conversion)
- **Geocoding** — Client-side geocoding via OpenStreetMap Nominatim
- **Email notifications** — Daily start/end alerts and CRUD notifications via the Resend API
- **Admin panel** — Manage people, families, and notification settings
- **Single shared password** — Simple auth via Flask-Login (one password for the whole family)

## Tech Stack

- **Backend:** Python / Flask, SQLAlchemy, Flask-Migrate (Alembic)
- **Frontend:** Jinja2 templates, Pico CSS v2, Leaflet.js (all from CDN — no build step)
- **Database:** SQLite
- **Deployment:** Docker on Fly.io with a persistent volume
- **Email:** Resend API
- **Scheduled jobs:** GitHub Actions cron workflow
- **Testing:** pytest, freezegun

## Local Development

```bash
# Install dependencies
uv sync

# Run database migrations
uv run flask db upgrade

# Start the dev server
uv run flask --app app:create_app run

# Run tests
uv run pytest
```

### Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | `"dev-secret-change-me"` | Flask session secret |
| `APP_PASSWORD` | `"family"` | Shared login password |
| `DATABASE_URL` | `sqlite:///app.db` | Database connection string |
| `RESEND_API_KEY` | *(none)* | Resend email API key |
| `RESEND_FROM_EMAIL` | *(none)* | Sender address |
| `OPENAI_API_KEY` | *(none)* | OpenAI API key (`gpt-image-2`) for AI cartoon map |

## Project Structure

```
app/
  __init__.py      # App factory, DB/login/migrate init
  models.py        # SQLAlchemy models (Family, Person, Trip, TripStop, Config)
  auth.py          # /login, /logout blueprint
  trips.py         # Dashboard, trip CRUD blueprint
  admin.py         # /admin people & family management
  email.py         # Resend API email helpers
  cli.py           # flask send-notifications CLI command
  filters.py       # Jinja2 template filters (flight_link, group_by_family)
  seed.py          # Default family member and family seeding
  templates/       # Jinja2 templates (Pico CSS v2)
  static/style.css # Custom styles and map styling
tests/
  conftest.py      # Fixtures and test helpers
  test_app_factory.py
  test_auth.py
  test_admin.py
  test_models.py
  test_trips.py
  test_trip_stops.py
  test_email.py
  test_cli.py
migrations/        # Alembic migrations (Flask-Migrate)
config.py          # Flask configuration from env vars
Dockerfile         # Python 3.13-slim container with uv
fly.toml           # Fly.io deployment config
```

## Deployment (Fly.io)

The app runs on Fly.io (`ord` region) with a persistent SQLite volume mounted at `/data`. Auto-stop is enabled to save resources — the machine starts on demand when a request arrives.

### Initial Setup

```bash
fly auth login
fly launch
fly volumes create data --region ord --size 1
```

### Family Reference Photo

The AI cartoon map uses a labeled reference photo of your family so OpenAI's `gpt-image-2` can draw recognizable cartoon versions. This file is kept off the public repo for privacy and stored on the Fly.io persistent volume.

1. Create a labeled photo of your family (each person's name visible) and save it as `family_reference.png`
2. Upload it to the persistent volume:
   ```bash
   fly ssh sftp shell
   put family_reference.png /data/family_reference.png
   ```
3. For local development, place the file at `app/static/family_reference.png` (this path is gitignored)

### Set Secrets

```bash
fly secrets set SECRET_KEY="<generate-a-strong-random-key>"
fly secrets set APP_PASSWORD="<your-family-password>"
fly secrets set RESEND_API_KEY="<your-resend-api-key>"
fly secrets set RESEND_FROM_EMAIL="Your Name <notifications@yourdomain.com>"
fly secrets set OPENAI_API_KEY="<your-openai-api-key>"
```

`DATABASE_URL` is already configured in `fly.toml` to point at the persistent volume (`sqlite:////data/app.db`).

### Deploy

```bash
fly deploy
```

Migrations run automatically on startup (`flask db upgrade` in the Dockerfile `CMD`).

### Useful Commands

```bash
fly logs          # View logs
fly ssh console   # SSH into the running machine
fly open          # Open the app in browser
fly status        # Check app status
```

### Scheduled Notifications

A GitHub Actions workflow (`.github/workflows/daily-notifications.yml`) runs daily at 8 AM ET. It wakes the Fly.io machine via HTTP, then SSHes in to run `flask send-notifications`.

To set this up:

1. Generate an org-scoped Fly API token (deploy tokens lack SSH access):
   ```bash
   fly tokens create org
   ```
2. Add the token as a GitHub repository secret named `FLY_API_TOKEN`
3. The workflow can also be triggered manually from the Actions tab
