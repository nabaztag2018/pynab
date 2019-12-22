# Adaptation du modèle d'ASR à la grammaire Nabaztag
----------------------------------------------------

Ce répertoire comprend un script (`adapt-model.sh`) pour créer un nouveau modèle
adapté de reconnaissance vocale à partir d'une grammaire
(`nabaztag-grammar-fr.jsgf`) et d'un lexique (`dict-fr-nabaztag.ipa`)

Il requiert [docker](https://github.com/docker/docker.github.io/issues/6910).

## Utilisation

1. Installer `docker`
2. Modifier `nabaztag-grammar-fr.jsgf`
3. Modifier `dict-fr-nabaztag.ipa`
4. Exécuter `sh adapt-model.sh fr`
5. (optionnellement) nettoyer :

    ````
    docker container prune
    docker image ls -a
    docker image rm ...
    ````

6. Installer et décompresser le modèle (`kaldi-nabaztag-fr-adapt-r*.tar.xz`) sur le Raspberry Pi, dans /opt/kaldi/model/
7. Configurer nabd pour utiliser ce modèle dans `nabd/asr.py`

# ASR model specialization for Nabaztag grammar
-----------------------------------------------

This repository contains a script (`adapt-model.sh`) used to create specialized
ASR model from a grammar (`nabaztag-grammar-en.jsgf`) and a dictionary
(`dict-en-nabaztag.ipa`)

It requires [docker](https://github.com/docker/docker.github.io/issues/6910).

## Usage

1. Install `docker`
2. Modify `nabaztag-grammar-fr.jsgf`
3. Modify `dict-fr-nabaztag.ipa`
4. Exécute `sh adapt-model.sh en`
5. (optionally) cleanup :

    ````
    docker container prune
    docker image ls -a
    docker image rm ...
    ````

6. Install and uncompress resulting model (`kaldi-nabaztag-en-adapt-r*.tar.xz`) on the Pi, in /opt/kaldi/model/
7. Configure nabd to use this new model in `nabd/asr.py`
