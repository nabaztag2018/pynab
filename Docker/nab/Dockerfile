FROM python:3.7-buster

RUN apt-get update && apt-get install -y \
    postgresql-client \
    libasound2-dev

COPY *.sh /usr/local/bin/

# Fake rpi-issue file used by nabweb
RUN echo "Raspberry Pi reference 1970-01-01" > /etc/rpi-issue

# Make /var/log/ writable for service log files, /run for PID files
RUN chmod a+w /var/log /run

# FIXME: Cannot run as non-root user, as we need to write a file in
# /var/run/postgresql to indicate that DB migrations have completed
# Need to find a better way to notify the containers

# RUN groupadd -g 1000 pi
# RUN useradd -u 1000 -m pi -g pi -s /bin/bash
# USER pi

RUN mkdir -p /home/pi/pynab
WORKDIR /home/pi/pynab

ENV VIRTUAL_ENV=/home/pi/venv
RUN python3.7 -m venv ${VIRTUAL_ENV}
ENV PATH=${VIRTUAL_ENV}/bin:${PATH}

COPY ./requirements_docker.txt /tmp
RUN ${VIRTUAL_ENV}/bin/pip install -r /tmp/requirements_docker.txt

ENV PYNAB_DEVELOPMENT=true

EXPOSE 8000
