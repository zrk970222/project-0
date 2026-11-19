# Project 0 — Tuesday (2026-11-17): Docker
# Grounded in the actual skeleton: app.main:app, port 8000,
# config reads PROJECT0_HOST / PROJECT0_PORT / PROJECT0_API_KEY from env.
FROM python:3.12-slim

WORKDIR /app

# Dependencies first so rebuilds stay cached when only app code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Run as non-root; the container must listen on 0.0.0.0 (the app
# defaults to 127.0.0.1, which is unreachable from outside a container).
RUN useradd --create-home appuser
RUN chown -R appuser:appuser /app
USER appuser

ENV PROJECT0_HOST=0.0.0.0 \
    PROJECT0_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

