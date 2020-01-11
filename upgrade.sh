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
    echo "Stopping services" > /tmp/pynab.upgrade
    # stop services using service files.
    for service_file in */*.service ; do
      name=`basename ${service_file}`
      if [ "${name}" != "nabd.service" -a "${name}" != "nabweb.service" ]; then
        sudo systemctl stop ${name} || echo -n ""
      fi
    done
    sudo systemctl stop nabd.socket || echo -n ""
    sudo systemctl stop nabd.service || echo -n ""
  
    sudo -u ${owner} touch /tmp/pynab.upgrade
    sudo chown ${owner} /tmp/pynab.upgrade
    echo "Updating code - 1/?" > /tmp/pynab.upgrade
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
    sudo -u ${owner} bash install.sh --upgrade
    sudo rm -f /tmp/pynab.upgrade
esac
