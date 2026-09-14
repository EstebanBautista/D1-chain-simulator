FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# requirements.txt first, source second: editing code reuses the dependency
# layer from cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# The gateway keeps its records here, on its own volume, well away from the
# store's PostgreSQL database. The directory is owned by the unprivileged user
# the process runs as, so it can still write its SQLite file.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app
USER appuser

EXPOSE 5000

CMD ["flask", "--app", "app.main:app", "run", "--host", "0.0.0.0", "--port", "5000"]
