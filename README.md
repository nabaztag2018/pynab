# Noyau Nabaztag en Python pour Raspberry Pi pour Paris Maker Faire 2018

[![Build Status](https://travis-ci.org/nabaztag2018/pynab.svg?branch=master)](https://travis-ci.org/nabaztag2018/pynab)

# Architecture

- nabd : daemon qui gère le lapin (i/o, chorégraphies)
- nabclockd : daemon pour le service horloge
- nabsurprised : daemon pour le service surprises
- nabtaichid : daemon pour le service taichi
- nabmastodond : daemon pour le service mastodon

