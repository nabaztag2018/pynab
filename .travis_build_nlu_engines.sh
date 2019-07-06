#!/bin/sh

# Prepare and compile snips engines, for travis.
# Regular installs should use install.sh script instead.
cd /home/travis/build/nabaztag2018/pynab/
python -m snips_nlu download fr
python -m snips_nlu download en

mkdir -p nabd/nlu
python -m snips_nlu generate-dataset en */nlu/intent_en.yaml > nabd/nlu/nlu_dataset_en.json
python -m snips_nlu generate-dataset fr */nlu/intent_fr.yaml > nabd/nlu/nlu_dataset_fr.json

if [ -d nabd/nlu/engine_en ]; then
  rm -rf nabd/nlu/engine_en
fi
snips-nlu train nabd/nlu/nlu_dataset_en.json nabd/nlu/engine_en

if [ -d nabd/nlu/engine_fr ]; then
  rm -rf nabd/nlu/engine_fr
fi
snips-nlu train nabd/nlu/nlu_dataset_fr.json nabd/nlu/engine_fr
