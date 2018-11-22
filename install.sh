#!/usr/bin/env bash

set -xuo pipefail
trap 's=$?; echo "$0: Error on line "$LINENO": $BASH_COMMAND"; exit $s' ERR
IFS=$'\n\t'

if [ "${1:-}" != "travis-chroot" -a "`uname -s -m`" != 'Linux armv6l' ]; then
  echo "Installation only planned on Raspberry Pi Zero, will cowardly exit"
  exit 1
fi

if [ $USER == "root" ]; then
  echo "Please run this script as a regular user with sudo privileges"
fi

cd `dirname "$0"`
root_dir=`pwd`

if [ ! -d "venv" ]; then
  echo "Creating Python 3 virtual environment"
  pyvenv-3.5 venv
fi

echo "Installing PyPi requirements"
venv/bin/pip install -r requirements.txt

trust=`sudo grep local /etc/postgresql/*/main/pg_hba.conf | grep -cE '^local +all +all +trust'`
if [ $trust -ne 1 ]; then
  echo "Configuring PostgreSQL for trusted access"
  sudo sed -i.orig -E -e 's|^(local +all +all +)peer$|\1trust|' /etc/postgresql/*/main/pg_hba.conf
  trust=`sudo grep local /etc/postgresql/*/main/pg_hba.conf | grep -cE '^local +all +all +trust'`
  if [ $trust -ne 1 ]; then
    echo "Failed to configure PostgreSQL"
    exit 1
  fi
  if [ "${1:-}" == "travis-chroot" ]; then
    cluster_version=`echo /etc/postgresql/*/main/pg_hba.conf  | sed -E 's|/etc/postgresql/(.+)/(.+)/pg_hba.conf|\1|g'`
    cluster_name=`echo /etc/postgresql/*/main/pg_hba.conf  | sed -E 's|/etc/postgresql/(.+)/(.+)/pg_hba.conf|\2|g'`
    sudo -u postgres /usr/lib/postgresql/${cluster_version}/bin/pg_ctl start -D /etc/postgresql/${cluster_version}/${cluster_name}/
  else
    sudo systemctl restart postgresql
  fi
fi

if [ ! -e '/etc/nginx/sites-enabled/pynab' ]; then
  echo "Installing nginx configuration file"
  if [ -h '/etc/nginx/sites-enabled/default' ]; then
    sudo rm /etc/nginx/sites-enabled/default
  fi
  sudo cp nabweb/nginx-site.conf /etc/nginx/sites-enabled/pynab
  if [ "${1:-}" != "travis-chroot" ]; then
    sudo systemctl restart nginx
  fi
fi

psql -U pynab -c '' 2>/dev/null || {
  echo "Creating PostgreSQL database"
  sudo -u postgres psql -U postgres -c "CREATE USER pynab"
  sudo -u postgres psql -U postgres -c "CREATE DATABASE pynab OWNER=pynab"
  sudo -u postgres psql -U postgres -c "ALTER ROLE pynab CREATEDB"
}

venv/bin/python manage.py migrate
venv/bin/django-admin compilemessages

if [ "${1:-}" == "--test" ]; then
  echo "Running tests"
  sudo venv/bin/pytest
fi

if [ "${1:-}" == "travis-chroot" ]; then
  sudo -u postgres /usr/lib/postgresql/${cluster_version}/bin/pg_ctl stop -D /etc/postgresql/${cluster_version}/${cluster_name}/
fi

for service_file in */*.service ; do
  name=`basename ${service_file}`
  sudo sed -e "s|/home/pi/pynab|${root_dir}|g" < ${service_file} > /tmp/${name}
  sudo mv /tmp/${name} /lib/systemd/system/${name}
  sudo chown root /lib/systemd/system/${name}
  sudo systemctl enable ${name}
  if [ "${1:-}" != "travis-chroot" ]; then
    sudo systemctl restart ${name}
  fi
done
