FROM python:alpine

RUN apk add build-base

ADD ./rdfdp /opt/rdfdp
ADD ./example /usr/share/rdfdpdata
ADD ./requirements.txt /opt/rdfdp/requirements.txt

WORKDIR /opt/rdfdp

RUN pip install --upgrade pip setuptools
RUN pip install -r requirements.txt
RUN pip install gunicorn[gevent]>=23.0.0

RUN apk del build-base

ENV DATA_PATH=/usr/share/rdfdpdata/data
ENV QUERIES_PATH=/usr/share/rdfdpdata/queries
ENV TEMPLATE_PATH=/usr/share/rdfdpdata/templates

RUN adduser --no-create-home --disabled-password --uid 1000 --shell /bin/sh rdfdp

USER rdfdp

EXPOSE 8000

ENTRYPOINT [ "gunicorn", "app:app" ]
