# Noyau Nabaztag en Python pour Raspberry Pi pour Paris Maker Faire 2018

[![Build Status](https://travis-ci.org/nabaztag2018/pynab.svg?branch=master)](https://travis-ci.org/nabaztag2018/pynab)

# Images

Les [releases](/nabaztag2018/pynab/releases) sont des images de Raspbian Stretch Lite 2018-11-13 avec pynab pré-installé. Elles ont les mêmes réglages que [Raspbian](https://www.raspberrypi.org/downloads/raspbian/).

# Installation sur Raspbian

0. S'assurer que le raspbian est bien à jour

De fait, il faut une Raspbian pas trop ancienne, sinon toutes les dépendances ne seront pas bien installées.

```
sudo rpi-update
sudo apt update
sudo apt upgrade
```

1. Installer PostgreSQL et les paquets requis

```
sudo apt-get install postgresql git python3 python3-venv gettext nginx
```

2. Récupérer le code

```
git clone https://github.com/nabaztag2018/pynab.git
cd pynab
```

3. Lancer le script d'installation qui fait le reste, notamment l'installation et le démarrage des services via systemd.

```
bash install.sh
```

# Architecture

Cf le document [PROTOCOL.md](PROTOCOL.md)

- nabd : daemon qui gère le lapin (i/o, chorégraphies)
- nabclockd : daemon pour le service horloge
- nabsurprised : daemon pour le service surprises
- nabtaichid : daemon pour le service taichi
- nabmastodond : daemon pour le service mastodon
- nabweb : interface web pour la configuration
