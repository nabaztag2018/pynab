#!/bin/sh

# Script to generate a new adapted model using a grammar and a dictionary.
# Requires docker.

if [ $# -ne 1 ]; then
    echo "$0 fr|en"
    exit 1
fi
if [ $1 = "en" ]; then
    BASE_MODEL_URL=https://goofy.zamia.org/zamia-speech/asr-models/kaldi-generic-en-tdnn_250-r20190609.tar.xz
    MODEL_NAME=kaldi-generic-en-tdnn_250-r20190609
    GRAMMAR=nabaztag-grammar-en.jsgf
    DICTIONARY=dict-en-nabaztag.ipa
    OUTPUT_MODEL_NAME=nabaztag-en
elif [ $1 = "fr" ]; then
    BASE_MODEL_URL=https://github.com/pguyot/zamia-speech/releases/download/20190930/kaldi-generic-fr-tdnn_250-r20190930.tar.xz
    MODEL_NAME=kaldi-generic-fr-tdnn_250-r20190930
    GRAMMAR=nabaztag-grammar-fr.jsgf
    DICTIONARY=dict-fr-nabaztag.ipa
    OUTPUT_MODEL_NAME=nabaztag-fr
else
    echo "Syntax error. Expected fr or en, got $1"
    echo "Usage: $0 fr|en"
    exit 1
fi
DATE=`date +%Y%M%d`

if [[ "$(docker images -q zamia-speech:latest 2> /dev/null)" == "" ]]; then
    docker build -t zamia-speech .
fi
docker run -it -v ${PWD}:/nabaztag-asr/ zamia-speech bash /nabaztag-asr/adapt-model-i.sh $BASE_MODEL_URL $MODEL_NAME $GRAMMAR $DICTIONARY $OUTPUT_MODEL_NAME
