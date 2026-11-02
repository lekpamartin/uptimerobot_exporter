# syntax=docker/dockerfile:1

# Image of the target platform, only used as a filesystem: there is no RUN in this
# stage, so building for another architecture does not need QEMU emulation
FROM python:3.15-alpine3.24 AS base

# Runs on the build platform
FROM --platform=$BUILDPLATFORM python:3.15-alpine3.24 AS build
COPY --from=base / /rootfs
# pip is not needed at runtime and ships vendored libraries (urllib3, msgpack,
# setuptools) flagged by vulnerability scanners. Dependencies are installed as
# pure-Python wheels, so they work on every target architecture.
RUN rm -rf /rootfs/usr/local/bin/pip* \
    /rootfs/usr/local/lib/python3.*/site-packages/pip \
    /rootfs/usr/local/lib/python3.*/site-packages/pip-*.dist-info \
    && pip install --no-cache-dir --no-compile --target /rootfs/app/deps \
    --only-binary=:all: --platform any --implementation py --abi none \
    --python-version "$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')" \
    requests

FROM scratch
LABEL maintainer="LEKPA"
LABEL org.opencontainers.image.source="https://github.com/lekpamartin/uptimerobot_exporter"
LABEL org.opencontainers.image.description="UptimeRobot exporter for Prometheus"
LABEL org.opencontainers.image.licenses="Apache-2.0"

COPY --from=build /rootfs /
COPY files/exporter.py /app/exporter.py

# Environment of the python image is lost with scratch, set what is needed
ENV PATH=/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=C.UTF-8 \
    PYTHONPATH=/app/deps \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER nobody

EXPOSE 9705

# Targets / which does not call the UptimeRobot API
HEALTHCHECK CMD ["python3", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/' % os.environ.get('UPTIMEROBOT_SERVER_PORT', '9705'), timeout=5)"]

CMD ["python3", "/app/exporter.py"]
