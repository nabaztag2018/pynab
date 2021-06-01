# Nabaztag en Python pour Raspberry Pi

[![build (qemu)](https://github.com/nabaztag2018/pynab/actions/workflows/arm-runner.yml/badge.svg?branch=master)](https://github.com/nabaztag2018/pynab/actions/workflows/arm-runner.yml)
[![tests](https://github.com/nabaztag2018/pynab/actions/workflows/tests.yml/badge.svg?branch=master)](https://github.com/nabaztag2018/pynab/actions/workflows/tests.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Total alerts](https://img.shields.io/lgtm/alerts/g/nabaztag2018/pynab.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/nabaztag2018/pynab/alerts/)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/nabaztag2018/pynab.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/nabaztag2018/pynab/context:python)
[![codecov](https://codecov.io/gh/nabaztag2018/pynab/branch/master/graph/badge.svg)](https://codecov.io/gh/nabaztag2018/pynab)
[![Twitter](https://img.shields.io/twitter/follow/nabaztagtagtag?label=Follow&style=social)](https://twitter.com/nabaztagtagtag)

## Cartes

Ce système est conçu pour deux cartes pour **Nabaztag** (v1) et **Nabaztag:Tag** (v2) :
- Une carte réalisée pour [Maker Faire 2018](https://paris.makerfaire.com/maker/entry/1285/), qui ne fonctionne qu'avec les Nabaztag (sans micro ni RFID).
- Une nouvelle version de la carte, proposée via la [campagne Ulule en mai 2019](https://fr.ulule.com/le-retour-du-nabaztag/), qui fonctionne avec les Nabaztag et les Nabaztag:Tag (les micros sont sur la carte, ce qui permet aux Nabaztag de bénéficier aussi de la reconnaissance vocale).

Les schémas et fichiers de fabrication de ces deux cartes sont dans le repository [hardware](https://github.com/nabaztag2018/hardware), respectivement [`RPI_Nabaztag`](https://github.com/nabaztag2018/hardware/blob/master/RPI_Nabaztag.PDF) (2018) et [`tagtagtag_V2.0`](https://github.com/nabaztag2018/hardware/tree/master/tagtagtag_V2.0) (2019).

Pour être prévenu de la prochaine campagne, vous pouvez vous inscrire à la [liste de diffusion](https://tinyletter.com/nabaztag).

## Images

Les [releases](https://github.com/nabaztag2018/pynab/releases) sont des images de Raspberry Pi OS (Raspbian) Lite avec pynab pré-installé. Elles ont les mêmes réglages que [Raspberry Pi OS](https://www.raspberrypi.org/software/operating-systems/#raspberry-pi-os-32-bit).

Les releases actuelles (>0.7.x) ne fonctionnent que sur les cartes 2019 (cf [#44](https://github.com/nabaztag2018/pynab/issues/44)).

## Installation sur Raspberry Pi OS (pour développeurs!)

### 0. S'assurer que le système est bien à jour

Le script d'installation requiert désormais une version basée sur Debian 10 (Buster), pour bénéficier de Python 3.7.

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

  - Lecteur RFID : [pilote CR14](https://github.com/pguyot/cr14) (Nabaztag:tag uniquement, non requis sur les Nabaztag, mais installé par les mises à jour)

### 2. Installer PostgreSQL et les paquets requis

```sh
sudo apt-get install postgresql libpq-dev git python3 python3-venv python3-dev gettext nginx openssl libssl-dev libffi-dev libmpg123-dev libasound2-dev libatlas-base-dev libgfortran3 libopenblas-dev liblapack-dev zram-tools
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

Cf le [protocole nabd](PROTOCOL.md)

- `nabd` : daemon qui gère le lapin (i/o, chorégraphies)
- `nab8balld` : daemon pour le service gourou
- `nabairqualityd` : daemon pour le service de qualité de l'air
- `nabclockd` : daemon pour le service horloge
- `nabsurprised` : daemon pour le service surprises
- `nabtaichid` : daemon pour le service taichi
- `nabmastodond` : daemon pour le service mastodon
- `nabweatherd` : daemon pour le service météo
- `nabweb` : interface web pour la configuration

## Contribution

Vos contributions sont toujours les bienvenues ! Veuillez d'abord consulter les [directives de contribution](CONTRIBUTING.md).
