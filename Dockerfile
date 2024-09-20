FROM python:3.12.1-alpine

WORKDIR /usr/src/app/

COPY requirements.txt .

RUN \
    apk add postgresql-libs && \
    apk add --virtual .build-deps gcc musl-dev postgresql-dev && \
    python3 -m pip install -r requirements.txt

# RUN  apk --purge del .build-deps

COPY . .


EXPOSE 8000