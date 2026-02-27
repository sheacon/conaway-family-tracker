FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=app:create_app

CMD flask db upgrade && gunicorn -w 1 -b 0.0.0.0:8080 "app:create_app()"
