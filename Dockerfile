FROM python:3.13-alpine
LABEL maintainer="LEKPA"
LABEL org.opencontainers.image.source="https://github.com/lekpamartin/uptimerobot_exporter"
LABEL org.opencontainers.image.description="UptimeRobot exporter for Prometheus"
LABEL org.opencontainers.image.licenses="Apache-2.0"

RUN pip install --no-cache-dir --upgrade pip requests

COPY files/exporter.py /exporter.py

USER nobody

EXPOSE 9705

# Targets / which does not call the UptimeRobot API
HEALTHCHECK CMD wget -q -O /dev/null "http://127.0.0.1:${UPTIMEROBOT_SERVER_PORT:-9705}/" || exit 1

CMD [ "python", "-u", "/exporter.py" ]
