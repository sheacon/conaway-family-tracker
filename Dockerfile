FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

COPY . .

ENV FLASK_APP=app:create_app

CMD uv run --no-dev flask db upgrade && uv run --no-dev gunicorn -w 1 -b 0.0.0.0:8080 "app:create_app()"
