FROM python:3.14.0rc1-alpine3.22
LABEL maintainer="LEKPA"

COPY files/exporter.py /exporter.py

RUN pip install --no-cache-dir --upgrade requests pip

EXPOSE 9705

CMD [ "python", "/exporter.py" ]
