FROM python:3.7-buster

RUN apt-get update && apt-get install -y \
    postgresql-client gettext \
    libmpg123-dev libasound2-dev \
    wireless-tools sudo

COPY *.sh /usr/local/bin/

# Fake nabd systemd service file used to retrieve the working directory
RUN echo "WorkingDirectory=/home/pi/pynab" > /lib/systemd/system/nabd.service

# Fake systemd-time-wait-sync.service needed by nabclockd
RUN mkdir -p /run/systemd/timesync/ && touch /run/systemd/timesync/synchronized

# Naively fake systemctl, used to check if the SSH service is active
RUN ln -s /bin/false /bin/systemctl

# Make /var/log/ writable for service log files, /run for PID files
RUN chmod a+w /var/log /run

# Set timezone
RUN echo "Europe/Paris" > /etc/timezone
RUN ln -fs /usr/share/zoneinfo/Europe/Paris /etc/localtime

# Make sure piwheels is available for pip
RUN /bin/echo -e "[global]\nextra-index-url=https://www.piwheels.org/simple\n" > /etc/pip.conf

RUN groupadd -g 1000 pi
RUN useradd -u 1000 -m pi -g pi -s /bin/bash
RUN echo "pi ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/010_pi-nopasswd

USER pi

RUN mkdir -p /home/pi/pynab
WORKDIR /home/pi/pynab

ENV VIRTUAL_ENV=/home/pi/venv
RUN python3.7 -m venv ${VIRTUAL_ENV}
ENV PATH=${VIRTUAL_ENV}/bin:${PATH}

COPY requirements.txt /tmp/requirements.txt
RUN grep -v -e py-kaldi-asr -e snips-nlu < /tmp/requirements.txt > /tmp/requirements_docker.txt
RUN ${VIRTUAL_ENV}/bin/pip install -r /tmp/requirements_docker.txt

ENV NABD_HOST=pynab
ENV NABD_PORT_NUMBER=10543

EXPOSE 8000
EXPOSE 10543
EXPOSE 10544
