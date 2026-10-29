# Multi-stage Alpine build for lean production image
FROM python:3.11-alpine AS builder

WORKDIR /build
COPY requirements.txt constraints.txt ./
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt -c constraints.txt


FROM python:3.11-alpine

COPY --from=builder /install /usr/local

# Run as an unprivileged user that owns /app, so the SQLite fallback database can be written
RUN adduser -D app
WORKDIR /app
COPY --chown=app . .
RUN chown app /app
USER app

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD sh -c 'wget --quiet --tries=1 --spider "http://localhost:${PORT:-8000}/health"' || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
