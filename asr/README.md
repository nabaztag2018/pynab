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
4. Exécuter `sh adapt-model.sh`
5. (optionnellement) nettoyer :

    ````
    docker container prune
    docker image ls -a
    docker image rm ...
    ````

6. Installer et décompresser le modèle (`kaldi-nabaztag-fr-adapt-r*.tar.xz`) sur le Raspberry Pi, dans /opt/kaldi/model/
7. Configurer nabd pour utiliser ce modèle dans `nabd/asr.py`
