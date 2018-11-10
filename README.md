# Noyau Nabaztag en Python pour Raspberry Pi pour Paris Maker Faire 2018

[![Build Status](https://travis-ci.org/nabaztag2018/pynab.svg?branch=master)](https://travis-ci.org/nabaztag2018/pynab)

# Installation

1. Installer PostgreSQL ainsi que les paquets Python requis

```
virtualenv-3.7 venv
source venv/bin/activate
# source venv/bin/activate.csh avec (t)csh
pip install -r requirements.txt
```

2. Créer une base PostgreSQL pynab avec comme utilisateur pynab.

```
psql -U postgres -c "CREATE USER pynab"
psql -U postgres -c "CREATE DATABASE pynab OWNER=pynab"
```

# Démarrage

Configurer la base de données et démarrer le serveur :
```
python manage.py migrate
python manage.py runserver
```

Démarrer nabd et les services avec :
```
python -m nabd.nabd
```
...
```
python -m nabclockd.nabclockd
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
