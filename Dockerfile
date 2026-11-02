# syntax=docker/dockerfile:1

# Docker Hardened Images (https://docs.docker.com/dhi/), `docker login dhi.io` is required
ARG PYTHON_VERSION=3.13

# Runs on the build platform and only installs pure-Python wheels, so the result works
# on every target architecture without QEMU emulation
FROM --platform=$BUILDPLATFORM dhi.io/python:${PYTHON_VERSION}-dev AS build
ARG PYTHON_VERSION
RUN pip install --no-cache-dir --no-compile --target /app/deps \
    --only-binary=:all: --platform any --implementation py --abi none \
    --python-version "${PYTHON_VERSION}" \
    requests

# Runtime image: no shell, no package manager, runs as nonroot
FROM dhi.io/python:${PYTHON_VERSION}
LABEL maintainer="LEKPA"
LABEL org.opencontainers.image.source="https://github.com/lekpamartin/uptimerobot_exporter"
LABEL org.opencontainers.image.description="UptimeRobot exporter for Prometheus"
LABEL org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONPATH=/app/deps \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=build /app/deps /app/deps
COPY files/exporter.py /app/exporter.py

# Already the default of DHI runtime images, made explicit for scanners
USER 65532:65532

EXPOSE 9705

# Targets / which does not call the UptimeRobot API (no shell nor wget in the image)
HEALTHCHECK CMD ["python3", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/' % os.environ.get('UPTIMEROBOT_SERVER_PORT', '9705'), timeout=5)"]

CMD ["python3", "/app/exporter.py"]
