# Noyau Nabaztag en Python pour Raspberry Pi pour Paris Maker Faire 2018

[![Build Status](https://travis-ci.org/nabaztag2018/pynab.svg?branch=master)](https://travis-ci.org/nabaztag2018/pynab)

# Installation sur Raspbian

0. S'assurer que le raspbian est bien à jour

```
sudo rpi-update
sudo apt update
sudo apt upgrade
```

1. Installer PostgreSQL et les paquets requis

```
sudo apt-get install postgresql git python3
git clone https://github.com/nabaztag2018/pynab.git
cd pynab
pyvenv-3.5 venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Configurer l'accès à PostgreSQL en local sans mot de passe en modifiant ```/etc/postgresql/9.6/main/pg_hba.conf```

```
local   all             all                                     peer
```

en

```
local   all             all                                     trust
```

puis redémarrer PostgreSQL.

```
sudo service postgresql restart
```

(ou bien modifier le fichier settings.py dans pynab/nabweb/)

3. Créer une base PostgreSQL pynab avec comme utilisateur pynab.

```
sudo -u postgres psql -U postgres -c "CREATE USER pynab"
sudo -u postgres psql -U postgres -c "CREATE DATABASE pynab OWNER=pynab"
```

4. Lancer les tests
```
pytest
```

# Démarrage

Configurer la base de données et démarrer le serveur :
```
python manage.py migrate
python manage.py runserver
```

Démarrer nabd et les services avec :
```
python -m nabd.nabd &
python -m nabmastodond.nabmastodond &
python -m nabclockd.nabclockd &
```

(les mettre dans systemd ?)

# Tests

Les tests sont exécutés avec pytest.
Il faut permettre à l'utilisateur PostgreSQL pynab de créer des bases de données.

```
psql -U postgres -c "ALTER ROLE pynab CREATEDB"
```

# Architecture

Cf le document [PROTOCOL.md](PROTOCOL.md)

- nabd : daemon qui gère le lapin (i/o, chorégraphies)
- nabclockd : daemon pour le service horloge
- nabsurprised : daemon pour le service surprises
- nabtaichid : daemon pour le service taichi
- nabmastodond : daemon pour le service mastodon
- nabweb : interface web pour la configuration
