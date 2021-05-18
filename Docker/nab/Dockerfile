FROM python:3.7-buster

RUN apt-get update && apt-get install -y \
    postgresql-client \
    libasound2-dev \
    sudo \
    netcat-openbsd \
    libmpg123-dev

COPY *.sh /usr/local/bin/

RUN echo "pi ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/010_pi-nopasswd 

# Fake rpi-issue file used by nabweb
RUN echo "Raspberry Pi reference 1970-01-01" > /etc/rpi-issue

# Fake nabd systemd service file used to retrieve the working directory
RUN echo "WorkingDirectory=/home/pi/pynab" > /lib/systemd/system/nabd.service

# Fake systemd-time-wait-sync.service needed by nabclockd
RUN mkdir -p /run/systemd/timesync/ && touch /run/systemd/timesync/synchronized

# Naively fake systemctl, used to check if the SSH service is active
RUN ln -s /bin/false /bin/systemctl

# Make /var/log/ writable for service log files, /run for PID files
RUN chmod a+w /var/log /run

RUN groupadd -g 1000 pi
RUN useradd -u 1000 -m pi -g pi -s /bin/bash

# FIXME: Cannot run as non-root user, as we need to write a file in
# /var/run/postgresql to indicate that DB migrations have completed
# Need to find a better way to notify the containers

# USER pi

RUN mkdir -p /home/pi/pynab

WORKDIR /home/pi/pynab

ENV VIRTUAL_ENV=/home/pi/venv
RUN python3.7 -m venv ${VIRTUAL_ENV}
ENV PATH=${VIRTUAL_ENV}/bin:${PATH}

COPY requirements.txt /tmp/requirements.txt
RUN grep -vE py-kaldi-asr < /tmp/requirements.txt > /tmp/requirements_docker.txt
RUN ${VIRTUAL_ENV}/bin/pip install -r /tmp/requirements_docker.txt

ENV NABD_HOST=nabd
ENV NABD_PORT_NUMBER=10543

EXPOSE 8000
EXPOSE 10543
EXPOSE 10544
