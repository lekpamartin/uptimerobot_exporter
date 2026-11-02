FROM python:3.13-alpine
LABEL maintainer="LEKPA"
LABEL org.opencontainers.image.source="https://github.com/lekpamartin/uptimerobot_exporter"
LABEL org.opencontainers.image.description="UptimeRobot exporter for Prometheus"
LABEL org.opencontainers.image.licenses="Apache-2.0"

RUN pip install --no-cache-dir --upgrade pip requests

COPY files/exporter.py /exporter.py

USER nobody

EXPOSE 9705

CMD [ "python", "-u", "/exporter.py" ]
