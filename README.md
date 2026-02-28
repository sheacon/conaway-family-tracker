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

## Deployment (Fly.io)

The app runs on Fly.io (`ord` region) with a persistent SQLite volume mounted at `/data`. Auto-stop is enabled to save resources — the machine starts on demand when a request arrives.

### Initial Setup

```bash
# Install the Fly CLI (https://fly.io/docs/flyctl/install/)
# Then authenticate
fly auth login

# Launch the app (creates the app and volume on first run)
fly launch

# Create the persistent volume for SQLite
fly volumes create data --region ord --size 1
```

### Set Secrets

Production secrets are set via `fly secrets` (not in `fly.toml`):

```bash
fly secrets set SECRET_KEY="<generate-a-strong-random-key>"
fly secrets set APP_PASSWORD="<your-family-password>"
fly secrets set RESEND_API_KEY="<your-resend-api-key>"
fly secrets set RESEND_FROM_EMAIL="Your Name <notifications@yourdomain.com>"
```

`DATABASE_URL` is already configured in `fly.toml` to point at the persistent volume (`sqlite:////data/app.db`).

### Deploy

```bash
fly deploy
```

Migrations run automatically on startup (`flask db upgrade` in the Dockerfile `CMD`).

### Useful Commands

```bash
# View logs
fly logs

# SSH into the running machine
fly ssh console

# Open the app in your browser
fly open

# Check app status
fly status
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
