FROM docker.io/python:3.14-alpine AS base

FROM base AS build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV VIRTUAL_ENV=/opt/venv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

ADD ./rdfproxy /opt/rdfproxy
ADD ./pyproject.toml /opt/rdfproxy/pyproject.toml
ADD ./uv.lock /opt/rdfproxy/uv.lock

WORKDIR /opt/rdfproxy

RUN uv venv /opt/venv
RUN uv sync --active --no-dev --all-extras --locked

FROM base

COPY --from=build /opt/venv /opt/venv
COPY --from=build /opt/rdfproxy /opt/rdfproxy
ADD ./example/rdfproxy /usr/share/rdfproxy

WORKDIR /opt/rdfproxy

RUN adduser --no-create-home --disabled-password --uid 1000 python

USER python

ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8000

ENTRYPOINT [ "gunicorn", "app:app" ]
