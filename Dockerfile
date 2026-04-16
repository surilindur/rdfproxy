FROM docker.io/alpine:latest

RUN apk add --no-cache uv

ADD ./rdfproxy /opt/rdfproxy
ADD ./example/rdfproxy /usr/share/rdfproxy
ADD ./.python-version /opt/rdfproxy/.python-version
ADD ./pyproject.toml /opt/rdfproxy/pyproject.toml
ADD ./uv.lock /opt/rdfproxy/uv.lock

RUN adduser --no-create-home --disabled-password --uid 1000 python

WORKDIR /opt/rdfproxy

RUN uv python install && uv sync --no-dev && uv pip install gunicorn[gevent]

USER python

EXPOSE 8000

ENTRYPOINT [ "uv", "run", "gunicorn", "app:app" ]
