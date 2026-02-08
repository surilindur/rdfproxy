FROM docker.io/python:alpine

# RUN apk add --no-cache build-base

ADD ./rdfproxy /opt/rdfproxy
ADD ./example/rdfproxy /usr/share/rdfproxy
ADD ./requirements.txt /opt/rdfproxy/requirements.txt

RUN adduser --no-create-home --disabled-password --uid 1000 python

WORKDIR /opt/rdfproxy

RUN pip install --no-cache-dir --root-user-action ignore --upgrade pip setuptools
RUN pip install --no-cache-dir --root-user-action ignore --requirement requirements.txt
RUN pip install --no-cache-dir --root-user-action ignore gunicorn[gevent]

USER python

EXPOSE 8000

ENTRYPOINT [ "gunicorn", "app:app" ]
