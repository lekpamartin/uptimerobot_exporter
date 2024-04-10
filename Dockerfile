FROM python:3.13.0a6-alpine3.19
LABEL maintainer="LEKPA"

COPY files/exporter.py /exporter.py

RUN pip install --no-cache-dir --upgrade requests pip

EXPOSE 9705

CMD [ "python", "/exporter.py" ]
