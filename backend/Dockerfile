FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# IANA tz data for ZoneInfo("Europe/Moscow")
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/*

# Dependencies + app package from pyproject.toml
COPY pyproject.toml alembic.ini ./
COPY migrations ./migrations
COPY app ./app
RUN pip install .

# SQLite lives here (mounted as a volume in docker-compose.yml)
RUN mkdir -p /data
ENV DB_PATH=/data/crm.db

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
