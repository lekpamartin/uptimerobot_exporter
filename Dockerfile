FROM python:alpine
LABEL maintainer="LEKPA"

COPY files/exporter.py /exporter.py

RUN pip install --no-cache-dir --update requests pip

CMD [ "python", "/exporter.py" ]
