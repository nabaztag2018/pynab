#!/bin/sh

# Script to generate a new adapted model using a grammar and a dictionary.
# Requires docker.

DATE=`date +%Y%M%d`
BASE_MODEL_URL=https://github.com/pguyot/zamia-speech/releases/download/20190930/kaldi-nabaztag-fr-r20191001.tar.xz
MODEL_NAME=kaldi-nabaztag-fr-r20191001
GRAMMAR=nabaztag-grammar-fr.jsgf
DICTIONARY=dict-fr-nabaztag.ipa
OUTPUT_MODEL_NAME=nabaztag-fr

if [[ "$(docker images -q zamia-speech:latest 2> /dev/null)" == "" ]]; then
    docker build -t zamia-speech .
fi
docker run -it -v ${PWD}:/nabaztag-asr/ zamia-speech bash /nabaztag-asr/adapt-model-i.sh $BASE_MODEL_URL $MODEL_NAME $GRAMMAR $DICTIONARY $OUTPUT_MODEL_NAME
