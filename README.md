# Nabaztag en Python pour Raspberry Pi

[![build (qemu)](https://github.com/nabaztag2018/pynab/actions/workflows/arm-runner.yml/badge.svg?branch=master)](https://github.com/nabaztag2018/pynab/actions/workflows/arm-runner.yml)
[![tests](https://github.com/nabaztag2018/pynab/actions/workflows/tests.yml/badge.svg?branch=master)](https://github.com/nabaztag2018/pynab/actions/workflows/tests.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![codecov](https://codecov.io/gh/nabaztag2018/pynab/branch/master/graph/badge.svg)](https://codecov.io/gh/nabaztag2018/pynab)
[![Twitter](https://img.shields.io/twitter/follow/nabaztagtagtag?label=Follow&style=social)](https://twitter.com/nabaztagtagtag)

## Cartes

Ce système est conçu pour deux cartes pour **Nabaztag** (v1) et **Nabaztag:Tag** (v2) :
- Une carte réalisée pour [Maker Faire 2018](https://paris.makerfaire.com/maker/entry/1285/), qui ne fonctionne qu'avec les Nabaztag (sans micro ni RFID).
- Une nouvelle version de la carte, proposée via les campagnes Ulule de [mai 2019](https://fr.ulule.com/le-retour-du-nabaztag/) et [octobre 2021](https://fr.ulule.com/l-eternel-retour-du-nabaztag/), qui fonctionne avec les Nabaztag et les Nabaztag:Tag (les micros sont sur la carte, ce qui permet aux Nabaztag de bénéficier aussi de la reconnaissance vocale).

Les schémas et fichiers de fabrication de ces deux cartes sont dans le repository [hardware](https://github.com/nabaztag2018/hardware), respectivement [`RPI_Nabaztag`](https://github.com/nabaztag2018/hardware/blob/master/RPI_Nabaztag.PDF) (2018) et [`tagtagtag_V2.0`](https://github.com/nabaztag2018/hardware/tree/master/tagtagtag_V2.0) (2019).

## Images

Les [releases](https://github.com/nabaztag2018/pynab/releases) sont des images de [Raspberry Pi OS](https://www.raspberrypi.org/software/operating-systems/) Lite ou [DietPi](https://dietpi.com/) avec Pynab pré-installé.

Les releases actuelles (>0.7.x) ne fonctionnent pas sur les cartes 2018 (cf [#44](https://github.com/nabaztag2018/pynab/issues/44)).

## Installation sur Raspberry Pi OS ou DietPi (pour développeurs!)

### 0. S'assurer que le système est bien à jour

Le script d'installation requiert une version basée sur Debian 11 (Bullseye), avec Python 3.9.

Debian 10 (Buster), avec Python 3.7 ([Raspberry Pi OS Legacy](https://www.raspberrypi.com/software/operating-systems/#raspberry-pi-os-legacy)), est aussi supporté.

Il est nécessaire que les 'kernel headers' installés via `apt-get` correspondent à la version installée du noyau.

```sh
sudo apt-get update
sudo apt-get upgrade
```

### 1. Configurer les pilotes pour le son, les oreilles et le lecteur RFID et redémarrer.

- Son : le pilote dépend de votre carte TagTagTag:
   - Carte Maker Faire 2018 : [pilote HiFiBerry](https://web.archive.org/web/20170914003528/support.hifiberry.com/hc/en-us/articles/205377651-Configuring-Linux-4-x-or-higher)
   - Carte Ulule 2019 : [pilote WM8960 - branche tagtagtag-sound](https://github.com/pguyot/wm8960/tree/tagtagtag-sound)

 - Oreilles : [pilote tagtagtag-ears](https://github.com/pguyot/tagtagtag-ears)

 - Lecteur RFID :
   - [pilote CR14](https://github.com/pguyot/cr14) (Nabaztag:tag uniquement, non requis sur les Nabaztag, mais installé par les mises à jour)
   - [pilote st25r391x](https://github.com/pguyot/st25r391x) (carte NFC 2022 pour Nabaztag & Nabaztag:tag)

Les 'kernel headers' sont nécessaires pour la compilation des pilotes:
```sh
sudo apt-get install gcc make raspberrypi-kernel-headers
```

### 2. Installer PostgreSQL et les paquets requis

```sh
sudo apt-get install postgresql libpq-dev git python3 python3-venv python3-dev gettext nginx openssl libssl-dev libffi-dev libmpg123-dev libasound2-dev libatlas-base-dev libgfortran5 libopenblas-dev liblapack-dev zram-tools
```
Sur DietPi les paquets suivants sont aussi nécessaires:
```sh
sudo apt-get install alsa-utils xz-utils avahi-daemon
```

### 3. Récupérer le code

```sh
git clone https://github.com/nabaztag2018/pynab.git
cd pynab
```

### 4. Lancer le script d'installation
Ce script fait le reste, notamment l'installation et le démarrage des services via `systemd`.

```sh
bash install.sh
```

ou, pour les cartes de la Maker Faire 2018 :

```sh
bash install.sh --makerfaire2018
```

## Mise à jour

A priori, cela fonctionne via l'interface web.
Si nécessaire, il est possible de le faire en ligne de commande avec :
```sh
cd pynab
bash upgrade.sh
```

## NabBlockly

[NabBlockly](https://github.com/pguyot/nabblockly), une interface de programmation des chorégraphies du lapin par blocs, est installé sur les images des releases depuis la 0.6.3b et fonctionne sur le port [8080](http://nabaztag.local:8080/). L'installation est possible sur le port 80 en modifiant la configuration de Nginx.

## Architecture

Voir le [protocole nabd](PROTOCOL.md)

- `nabd` : démon qui gère le lapin (e/s, chorégraphies)
- `nab8balld` : démon pour le service gourou
- `nabairqualityd` : démon pour le service de qualité de l'air
- `nabclockd` : démon pour le service horloge
- `nabsurprised` : démon pour le service surprises
- `nabtaichid` : démon pour le service taichi
- `nabmastodond` : démon pour le service mastodon
- `nabweatherd` : démon pour le service météo
- `nabiftttd` : démon pour le service IFTTT
- `nabweb` : interface web pour la configuration

## Contribution

Vos contributions sont toujours les bienvenues ! Veuillez d'abord consulter les [directives de contribution](CONTRIBUTING.md).
