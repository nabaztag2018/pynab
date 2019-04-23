# Noyau Nabaztag en Python pour Raspberry Pi pour Paris Maker Faire 2018

[![Build Status](https://travis-ci.org/nabaztag2018/pynab.svg?branch=master)](https://travis-ci.org/nabaztag2018/pynab)


# Carte Maker Faire2018

Ce noyau nécessite une carte spécifique réalisée pour Maker Faire 2018 qui connecte le raspberry Pi Zero et le Hat HifiBerry (miniAmp) avec les interfaces du Nabaztag (leds, HP, moteur, encodeur). 

Les schémas et fichiers de fabrication sont dans le repository "hardware".

# Images

Les [releases](https://github.com/nabaztag2018/pynab/releases) sont des images de Raspbian Stretch Lite 2018-11-13 avec pynab pré-installé. Elles ont les mêmes réglages que [Raspbian](https://www.raspberrypi.org/downloads/raspbian/).

# Installation sur Raspbian

0. S'assurer que le raspbian est bien à jour

De fait, il faut une Raspbian pas trop ancienne, sinon toutes les dépendances ne seront pas bien installées.
Il est nécessaire que les headers depuis le paquet apt correspondent à la version du noyau.

```
sudo apt update
sudo apt upgrade
```

1. Configurer la carte son et redémarrer.

v1 :
https://support.hifiberry.com/hc/en-us/articles/205377651-Configuring-Linux-4-x-or-higher

v2 :
http://wiki.seeedstudio.com/ReSpeaker_2_Mics_Pi_HAT/

2. Installer PostgreSQL et les paquets requis

```
sudo apt-get install postgresql libpq-dev git python3 python3-venv gettext nginx openssl libssl-dev libffi-dev libmpg123-dev pulseaudio libpulse-dev libalsaplayer-dev
```

3. Installer la version précompilée de kaldi pour Pi Zero

https://github.com/pguyot/kaldi/releases/tag/v5.4.1

```
wget https://github.com/pguyot/kaldi/releases/download/v5.4.1/kaldi-c3260f2-linux_armv6l-vfp.tgz
cd / && sudo tar xvf /home/pi/kaldi-c3260f2-linux_armv6l-vfp.tgz
```

4. Augmenter la taille du swap à 512 Mo

(nécessaire pour compiler l'interface de kaldi pour Python)

```
sudo vi /etc/dphys-swapfile
sudo /etc/init.d/dphys-swapfile restart
```

5. Récupérer le code

```
git clone https://github.com/nabaztag2018/pynab.git
cd pynab
```

6. Lancer le script d'installation qui fait le reste, notamment l'installation et le démarrage des services via systemd.

```
bash install.sh
```

# Mise à jour

A priori, cela fonctionne via l'interface.
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
