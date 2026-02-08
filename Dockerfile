FROM python:alpine

RUN apk add --no-cache build-base libstdc++

ADD ./rdfgp /opt/rdfgp
ADD ./example/templates /usr/share/rdfgp
ADD ./requirements.txt /opt/rdfgp/requirements.txt

RUN adduser --disabled-password --uid 1000 --shell /bin/sh python
RUN chown --recursive python:python /opt/rdfgp

USER python

WORKDIR /opt/rdfgp

RUN pip install --no-cache-dir --user --upgrade pip setuptools
RUN pip install --no-cache-dir --user --requirement requirements.txt
RUN pip install --no-cache-dir --user gunicorn[gevent]

EXPOSE 8000

ENTRYPOINT [ "gunicorn", "app:app" ]
