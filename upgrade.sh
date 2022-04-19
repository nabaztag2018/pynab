#!/usr/bin/env bash

set -uo pipefail
trap 's=$?; echo "$0: Error on line "$LINENO": $BASH_COMMAND"; exit $s' ERR
IFS=$'\n\t'

root_dir=`sed -nE -e 's|WorkingDirectory=(.+)|\1|p' < /lib/systemd/system/nabd.service`
owner=`stat -c '%U' ${root_dir}`
uid=`stat -c '%u' ${root_dir}`

step="init"
if [ "${1:-}" == "install" ]; then
  step="install"
fi

case $step in
  "init")
    echo "Stopping services"
    echo "Stopping services" > /tmp/pynab.upgrade
    # stop services using service files.
    for service_file in */*.service ; do
      name=`basename ${service_file}`
      if [ "${name}" != "nabd.service" -a "${name}" != "nabweb.service" ]; then
        sudo systemctl stop ${name} || true
      fi
    done
    sudo systemctl stop nabd.socket || true
    sudo systemctl stop nabd.service || true
  
    echo "Updating Pynab"
    sudo -u ${owner} touch /tmp/pynab.upgrade
    sudo chown ${owner} /tmp/pynab.upgrade
    echo "Updating Pynab - 1/?" > /tmp/pynab.upgrade
    cd ${root_dir}
    if [[ $EUID -ne ${uid} ]]; then
      sudo -u ${owner} git pull
    else
      git pull
    fi
  
    bash upgrade.sh "install"
    ;;
  "install")
    cd ${root_dir}
    sudo -u ${owner} bash install.sh --upgrade
    sudo rm -f /tmp/pynab.upgrade
esac
