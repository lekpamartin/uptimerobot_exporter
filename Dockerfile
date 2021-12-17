FROM python:alpine
LABEL maintainer="LEKPA"

COPY files/exporter.py /exporter.py

RUN pip install --no-cache-dir --upgrade requests pip

EXPOSE 9705

CMD [ "python", "/exporter.py" ]
