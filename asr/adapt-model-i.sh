#!/bin/sh

if [ $# != 5 ]; then
    "Syntax: $0 BASE_MODEL_URL INPUT_MODEL_NAME GRAMMAR DICTIONARY OUTPUT_MODEL_NAME"
    exit 1
fi
if [ ! -e /opt/kaldi ]; then
    "Kaldi is supposed to be installed at /opt/kaldi"
    exit 1
fi
if [ ! -e /zamia-speech ]; then
    "zamia-speech is supposed to be installed at /zamia-speech"
    exit 1
fi

BASE_MODEL_URL=$1
INPUT_MODEL_NAME=$2
GRAMMAR=$3
DICTIONARY=$4
OUTPUT_MODEL_NAME=$5

if [ ! -e /nabaztag-asr/$GRAMMAR ]; then
    "$GRAMMAR not found in /nabaztag-asr/"
    exit 1
fi
if [ ! -e /nabaztag-asr/$DICTIONARY ]; then
    "$DICTIONARY not found in /nabaztag-asr/"
    exit 1
fi
if [ -e /nabaztag-asr/$INPUT_MODEL_NAME.tar.xz ]; then
    echo "Installing $INPUT_MODEL_NAME"
    mkdir -p /opt/kaldi/model/ && cd /opt/kaldi/model/ && tar xJf /nabaztag-asr/$INPUT_MODEL_NAME.tar.xz || exit 1
else
    echo "Downloading and installing $INPUT_MODEL_NAME"
    mkdir -p /opt/kaldi/model/ && cd /opt/kaldi/model/ && wget -qO - $BASE_MODEL_URL | tar xJ || exit 1
fi

if [ ! -e /opt/kaldi/model/$INPUT_MODEL_NAME/ ]; then
    "model $INPUT_MODEL_NAME not found in /opt/kaldi/model/"
    exit 1
fi

echo "Copying dictionary $DICTIONARY"
cp /nabaztag-asr/$DICTIONARY /zamia-speech/data/src/dicts/ || exit 1

echo "Creating adapted model"
cd /zamia-speech/ && ./speech_kaldi_adapt.py /opt/kaldi/model/$INPUT_MODEL_NAME $DICTIONARY /nabaztag-asr/$GRAMMAR $OUTPUT_MODEL_NAME || exit 1

echo "Fixing adaptation script"
cd /zamia-speech/data/dst/asr-models/kaldi/$OUTPUT_MODEL_NAME || exit 1
sed -i.bak -e 's|nspc|<eps>|' run-adaptation.sh || exit 1

echo "Running adaptation"
./run-adaptation.sh || exit 1

echo "Exporting model to host"
cd /zamia-speech/ && ./speech_dist.sh $OUTPUT_MODEL_NAME kaldi adapt || exit 1
cp /zamia-speech/data/dist/asr-models/kaldi-$OUTPUT_MODEL_NAME-adapt-r*.tar.xz /nabaztag-asr/ || exit 1
