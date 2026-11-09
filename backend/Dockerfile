# Multi-stage Alpine build for lean production image
FROM python:3.11-alpine AS builder

WORKDIR /build
COPY requirements.txt constraints.txt ./
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt -c constraints.txt


FROM python:3.11-alpine

# Alpine's security fixes land between rebuilds of the base image, so take them now.
# Railway passes this in, so each deploy runs the upgrade again rather than reusing
# a cached result from an earlier build.
ARG RAILWAY_GIT_COMMIT_SHA
RUN apk upgrade --no-cache

COPY --from=builder /install /usr/local

# Run as an unprivileged user that can't change the code: root owns it, and the
# user can write only data/, where the SQLite fallback database goes
RUN adduser -D app
WORKDIR /app
COPY . .
RUN python -m compileall -q app && mkdir data && chown app data
USER app

ENV PYTHONUNBUFFERED=1
# Used only when Railway (or docker run -e) doesn't set DATABASE_URL
ENV DATABASE_URL=sqlite:////app/data/moodforecast.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD sh -c 'wget --quiet --tries=1 --spider "http://localhost:${PORT:-8000}/health"' || exit 1

# exec, so the stop signal reaches uvicorn and it can shut down cleanly
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-graceful-shutdown 10"]
