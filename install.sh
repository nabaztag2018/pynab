#!/usr/bin/env bash

set -xuo pipefail
trap 's=$?; echo "$0: Error on line "$LINENO": $BASH_COMMAND"; exit $s' ERR
IFS=$'\n\t'

# makerfaire2018: Paris Maker Faire 2018 card, only fits Nabaztag V1.
# (default): Ulule 2019 card, fits Nabaztag V1 and Nabaztag V2. Features a microphone. Button is on GPIO 17.
makerfaire2018=0

# travis-chroot : we're building a release image on Travis CI
travis_chroot=0

# test : user wants to run tests (good idea, makes sure sounds and leds are functional)
test=0

# upgrade : this script is invoked from upgrade.sh, typically from the button in the web interface.
upgrade=0

if [ "${1:-}" == "--makerfaire2018" ]; then
  makerfaire2018=1
  shift
fi

if [ "${1:-}" == "travis-chroot" ]; then
  travis_chroot=1
elif [ "${1:-}" == "test" ]; then
  test=1
elif [ "${1:-}" == "--upgrade" ]; then
  upgrade=1
  # auto-detect maker faire card here.
  if [ `aplay -L | grep -c "hifiberry"` -gt 0 ]; then
    makerfaire2018=1
  fi
fi

if [ "`uname -s -m`" != 'Linux armv6l' ]; then
  echo "Installation only planned on Raspberry Pi Zero, will cowardly exit"
  exit 1
fi

if [ $USER == "root" ]; then
  echo "Please run this script as a regular user with sudo privileges"
  exit 1
fi

cd `dirname "$0"`
root_dir=`pwd`
owner=`stat -c '%U' ${root_dir}`

if [ $travis_chroot -eq 0 -a $makerfaire2018 -eq 0 -a `aplay -L | grep -c "tagtagtagsound"` -eq 0 ]; then
  if [ `aplay -L | grep -c "hifiberry"` -gt 0 ]; then
    echo "Judging from the sound card, this looks likes a Paris Maker Faire 2018 card."
    echo "Please double-check and restart this script with --makerfaire2018"
  else
    echo "Please install and configure sound card driver https://github.com/pguyot/wm8960/tree/tagtagtag-sound"
  fi
  exit 1
fi

if [ $makerfaire2018 -eq 1 ]; then
  if [ `aplay -L | grep -c "hifiberry"` -eq 0 ]; then
    echo "Please install and configure sound card driver https://support.hifiberry.com/hc/en-us/articles/205377651-Configuring-Linux-4-x-or-higher"
    exit 1
  fi
fi

if [ $upgrade -eq 1 -a $makerfaire2018 -eq 0 -a -d /home/pi/wm8960 ]; then
  echo "Updating sound driver" > /tmp/pynab.upgrade
  cd /home/pi/wm8960
  sudo chown -R ${owner} .git
  pull=`git pull`
  if [ "$pull" != "Already up to date." ]; then
    make && sudo make install
    sudo touch /tmp/pynab.upgrade.reboot
  fi
else
  if [ $travis_chroot -eq 0 -a ! -e "/dev/ear0" ]; then
    echo "Please install ears driver https://github.com/pguyot/tagtagtag-ears"
    exit 1
  fi
fi

if [ $upgrade -eq 1 ]; then
  echo "Updating ears driver" > /tmp/pynab.upgrade
  if [ -d /home/pi/tagtagtag-ears ]; then
    cd /home/pi/tagtagtag-ears
    sudo chown -R ${owner} .git
    pull=`git pull`
    if [ "$pull" != "Already up to date." ]; then
      make && sudo make install
      sudo touch /tmp/pynab.upgrade.reboot
    fi
  else
    cd /home/pi
    git clone https://github.com/pguyot/tagtagtag-ears
    make && sudo make install
    sudo touch /tmp/pynab.upgrade.reboot
  fi
else
  if [ $travis_chroot -eq 0 -a ! -e "/dev/ear0" ]; then
    echo "Please install ears driver https://github.com/pguyot/tagtagtag-ears"
    exit 1
  fi
fi

if [ $makerfaire2018 -eq 0 ]; then
  if [ $upgrade -eq 1 ]; then
    echo "Updating ASR models" > /tmp/pynab.upgrade
  fi

  # maker faire card has no mic, no need to install kaldi
  if [ ! -d "/opt/kaldi" ]; then
    echo "Installing precompiled kaldi into /opt"
    wget -O - -q https://github.com/pguyot/kaldi/releases/download/v5.4.1/kaldi-c3260f2-linux_armv6l-vfp.tar.xz | sudo tar xJ -C /
    sudo ldconfig
  fi

  sudo mkdir -p "/opt/kaldi/model"

  if [ ! -d "/opt/kaldi/model/kaldi-generic-en-tdnn_250-r20190609" ]; then
    echo "Installing kaldi model for English from Zamia Speech"
    wget -O - -q https://goofy.zamia.org/zamia-speech/asr-models/kaldi-generic-en-tdnn_250-r20190609.tar.xz | sudo tar xJ -C /opt/kaldi/model/
  fi

  if [ ! -d "/opt/kaldi/model/kaldi-nabaztag-fr-r20191001" ]; then
    echo "Installing kaldi model for French"
    wget -O - -q https://github.com/pguyot/zamia-speech/releases/download/20190930/kaldi-nabaztag-fr-r20191001.tar.xz | sudo tar xJ -C /opt/kaldi/model
  fi
fi

cd $root_dir
if [ ! -d "venv" ]; then
  if ! [ -x "$(command -v python3.7)" ] ; then
    echo "Please install Python 3.7 (you might need to upgrade your Raspbian distribution)"
    exit 1
  fi

  echo "Creating Python 3.7 virtual environment"
  python3.7 -m venv venv
fi

echo "Installing PyPi requirements"
if [ $upgrade -eq 1 ]; then
  echo "Updating Python requirements" > /tmp/pynab.upgrade
fi
# Start with wheel which is required to compile some of the other requirements
venv/bin/pip install wheel
venv/bin/pip install -r requirements.txt

if [ $makerfaire2018 -eq 0 ]; then
  if [ $upgrade -eq 1 ]; then
    echo "Updating NLU models" > /tmp/pynab.upgrade
  fi

  # maker faire card has no mic, no need to install snips
  if [ ! -d "venv/lib/python3.7/site-packages/snips_nlu_fr" ]; then
    echo "Downloading snips_nlu models for French"
    venv/bin/python -m snips_nlu download fr
  fi

  if [ ! -d "venv/lib/python3.7/site-packages/snips_nlu_en" ]; then
    echo "Downloading snips_nlu models for English"
    venv/bin/python -m snips_nlu download en
  fi

  echo "Compiling snips datasets"
  mkdir -p nabd/nlu
  venv/bin/python -m snips_nlu generate-dataset en */nlu/intent_en.yaml > nabd/nlu/nlu_dataset_en.json
  venv/bin/python -m snips_nlu generate-dataset fr */nlu/intent_fr.yaml > nabd/nlu/nlu_dataset_fr.json

  echo "Persisting snips engines"
  if [ -d nabd/nlu/engine_en ]; then
    rm -rf nabd/nlu/engine_en
  fi
  venv/bin/snips-nlu train nabd/nlu/nlu_dataset_en.json nabd/nlu/engine_en
  if [ -d nabd/nlu/engine_fr ]; then
    rm -rf nabd/nlu/engine_fr
  fi
  venv/bin/snips-nlu train nabd/nlu/nlu_dataset_fr.json nabd/nlu/engine_fr
fi

trust=`sudo grep local /etc/postgresql/*/main/pg_hba.conf | grep -cE '^local +all +all +trust' || echo -n ''`
if [ $trust -ne 1 ]; then
  echo "Configuring PostgreSQL for trusted access"
  sudo sed -i.orig -E -e 's|^(local +all +all +)peer$|\1trust|' /etc/postgresql/*/main/pg_hba.conf
  trust=`sudo grep local /etc/postgresql/*/main/pg_hba.conf | grep -cE '^local +all +all +trust' || echo -n ''`
  if [ $trust -ne 1 ]; then
    echo "Failed to configure PostgreSQL"
    exit 1
  fi
  if [ $travis_chroot -eq 1 ]; then
    cluster_version=`echo /etc/postgresql/*/main/pg_hba.conf  | sed -E 's|/etc/postgresql/(.+)/(.+)/pg_hba.conf|\1|g'`
    cluster_name=`echo /etc/postgresql/*/main/pg_hba.conf  | sed -E 's|/etc/postgresql/(.+)/(.+)/pg_hba.conf|\2|g'`
    sudo -u postgres /usr/lib/postgresql/${cluster_version}/bin/pg_ctl start -D /etc/postgresql/${cluster_version}/${cluster_name}/
  else
    sudo systemctl restart postgresql
  fi
fi

if [ $upgrade -eq 0 ]; then
  if [ ! -e '/etc/nginx/sites-enabled/pynab' ]; then
    echo "Installing nginx configuration file"
    if [ -h '/etc/nginx/sites-enabled/default' ]; then
      sudo rm /etc/nginx/sites-enabled/default
    fi
    sudo cp nabweb/nginx-site.conf /etc/nginx/sites-enabled/pynab
    if [ $travis_chroot -eq 0 ]; then
      sudo systemctl restart nginx
    fi
  fi
else
  echo "Restarting Nginx" > /tmp/pynab.upgrade
  if [ -e '/etc/nginx/sites-enabled/pynab' ]; then
    sudo cp nabweb/nginx-site.conf /etc/nginx/sites-enabled/pynab
    sudo systemctl restart nginx
  fi
fi

psql -U pynab -c '' 2>/dev/null || {
  echo "Creating PostgreSQL database"
  sudo -u postgres psql -U postgres -c "CREATE USER pynab"
  sudo -u postgres psql -U postgres -c "CREATE DATABASE pynab OWNER=pynab"
  sudo -u postgres psql -U postgres -c "ALTER ROLE pynab CREATEDB"
}

if [ $upgrade -eq 1 ]; then
  echo "Updating data models" > /tmp/pynab.upgrade
fi
venv/bin/python manage.py migrate

if [ $upgrade -eq 0 ]; then
  venv/bin/django-admin compilemessages
else
  echo "Updating localization messages" > /tmp/pynab.upgrade
  for module in nab*/locale; do
    (
      cd `dirname ${module}`
      ../venv/bin/django-admin compilemessages
    )
  done
fi

if [ $test -eq 1 ]; then
  echo "Running tests"
  sudo venv/bin/pytest
fi

if [ $travis_chroot -eq 1 ]; then
  sudo -u postgres /usr/lib/postgresql/${cluster_version}/bin/pg_ctl stop -D /etc/postgresql/${cluster_version}/${cluster_name}/
fi

# copy service files
if [ $upgrade -eq 1 ]; then
  echo "Installing service files" > /tmp/pynab.upgrade
fi
for service_file in nabd/nabd.socket */*.service ; do
  name=`basename ${service_file}`
  sudo sed -e "s|/home/pi/pynab|${root_dir}|g" < ${service_file} > /tmp/${name}
  sudo mv /tmp/${name} /lib/systemd/system/${name}
  sudo chown root /lib/systemd/system/${name}
  sudo systemctl enable ${name}
done

if [ -e /tmp/pynab.upgrade.reboot ]; then
  echo "Upgrade requires reboot, rebooting now"
  sudo rm -f /tmp/pynab.upgrade
  sudo rm -f /tmp/pynab.upgrade.reboot
  sudo reboot
else
  if [ $travis_chroot -eq 0 ]; then
    if [ $upgrade -eq 1 ]; then
      echo "Restarting services" > /tmp/pynab.upgrade
    fi
    sudo systemctl start nabd.socket
    sudo systemctl start nabd.service

    # start services
    for service_file in */*.service ; do
      name=`basename ${service_file}`
      if [ "${name}" != "nabd.service" -a "${name}" != "nabweb.service" ]; then
        sudo systemctl start ${name}
      fi
    done

    if [ $upgrade -eq 1 ]; then
      echo "Restarting website" > /tmp/pynab.upgrade
      sudo systemctl restart nabweb.service
    else
      sudo systemctl start nabweb.service
    fi
  fi
fi
