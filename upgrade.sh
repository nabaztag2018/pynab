#!/usr/bin/env bash

set -xuo pipefail
trap 's=$?; echo "$0: Error on line "$LINENO": $BASH_COMMAND"; exit $s' ERR
IFS=$'\n\t'

root_dir=`sed -nE -e 's|WorkingDirectory=(.+)|\1|p' < /lib/systemd/system/nabd.service`
owner=`stat -c '%U' ${root_dir}`
ownerid=`stat -c '%u' ${root_dir}`

version="old"
if [ $# -eq 1 ]; then
  if [ "$1" == "newversion" ]; then
    version="new"
  fi
fi

case $version in
  "old")
    sudo systemctl stop nab8balld
    sudo systemctl stop nabsurprised
    sudo systemctl stop nabtaichid
    sudo systemctl stop nabclockd
    sudo systemctl stop nabmastodond
    sudo systemctl stop nabd
  
    cd ${root_dir}
    if [[ $EUID -ne ${ownerid} ]]; then
      sudo -u ${owner} git pull
    else
      git pull
    fi
  
    bash upgrade.sh "newversion"
    ;;
  "new")
    cd ${root_dir}
    venv/bin/python manage.py migrate
    for module in nab*/locale; do
      (
        cd `dirname ${module}`
        if [[ $EUID -ne ${ownerid} ]]; then
          sudo -u ${owner} ../venv/bin/django-admin compilemessages
        else
          ../venv/bin/django-admin compilemessages
        fi
      )
    done

    # new services
    sudo systemctl enable nab8balld

    sudo systemctl start nabd
    sudo systemctl start nabsurprised
    sudo systemctl start nabtaichid
    sudo systemctl start nabclockd
    sudo systemctl start nabmastodond
    sudo systemctl start nab8balld
    sudo systemctl restart nabweb
esac
