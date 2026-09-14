FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# requirements.txt first, source second: editing code reuses the dependency
# layer from cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Nothing here needs root.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# No port, no server: this is a worker. It polls its store's database and
# ships batches of invoices to head office.
CMD ["python", "-m", "app.main"]
