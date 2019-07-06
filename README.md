# Nabaztag en Python pour Raspberry Pi

[![Build Status](https://travis-ci.org/nabaztag2018/pynab.svg?branch=master)](https://travis-ci.org/nabaztag2018/pynab)

# Cartes

Ce système est conçu pour deux cartes :
- Une carte réalisée pour Maker Faire 2018, qui ne fonctionne qu'avec les Nabaztag v1 (sans micro ni RFID).
- Une nouvelle version de la carte, proposée via la campagne Ulule en mai 2019, qui fonctionne avec les Nabaztag v1 et v2 (les micros sont sur la carte, du coup les Nabaztag v1 bénéficient aussi de la reconnaissance vocale).

Les schémas et fichiers de fabrication de ces deux cartes sont dans le repository [hardware](https://github.com/nabaztag2018/hardware), respectivement [`RPI\_Nabaztag`](https://github.com/nabaztag2018/hardware/blob/master/RPI_Nabaztag.PDF) (2018) et [`pyNab\_v4.1`](https://github.com/nabaztag2018/hardware/blob/master/pyNab_V4.1_voice_reco.PDF) (2019).

# Images

Les [releases](https://github.com/nabaztag2018/pynab/releases) sont des images de Raspbian Stretch Lite 2018-11-13 avec pynab pré-installé. Elles ont les mêmes réglages que [Raspbian](https://www.raspberrypi.org/downloads/raspbian/).

La release actuelle (0.2.0) ne fonctionne que sur les cartes 2018.

# Installation sur Raspbian (pour développeurs !)

0. S'assurer que le système est bien à jour

Le script d'installation requiert désormais une Raspbian avec buster, pour bénéficier de Python 3.7.
Il est nécessaire que les headers depuis le paquet apt correspondent à la version du noyau.

```
sudo apt update
sudo apt upgrade
```

1. Configurer la carte son et redémarrer.

Maker Faire 2018 :
https://support.hifiberry.com/hc/en-us/articles/205377651-Configuring-Linux-4-x-or-higher

Ulule 2019 :
http://wiki.seeedstudio.com/ReSpeaker_2_Mics_Pi_HAT/

2. Installer PostgreSQL et les paquets requis

```
sudo apt-get install postgresql libpq-dev git python3 python3-venv gettext nginx openssl libssl-dev libffi-dev libmpg123-dev libasound2-dev libatlas-base-dev libgfortran3
```

3. Récupérer le code

```
git clone https://github.com/nabaztag2018/pynab.git
cd pynab
```

4. Lancer le script d'installation qui fait le reste, notamment l'installation et le démarrage des services via systemd.

```
bash install.sh
```

ou, pour les cartes Maker Faire 2018 :

```
bash install.sh --makerfaire2018
```

# Mise à jour

A priori, cela fonctionne via l'interface web.
Si nécessaire, il est possible de le faire en ligne de commande avec :
```
cd pynab
bash upgrade.sh
``` 

# Architecture

Cf le document [PROTOCOL.md](PROTOCOL.md)

- nabd : daemon qui gère le lapin (i/o, chorégraphies)
- nabclockd : daemon pour le service horloge
- nabsurprised : daemon pour le service surprises
- nabtaichid : daemon pour le service taichi
- nabmastodond : daemon pour le service mastodon
- nabweatherd : daemon pour le service météo
- nabweb : interface web pour la configuration
