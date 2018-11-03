# Noyau Nabaztag en Python pour Raspberry Pi pour Paris Maker Faire 2018

[![Build Status](https://travis-ci.org/nabaztag2018/pynab.svg?branch=master)](https://travis-ci.org/nabaztag2018/pynab)

# Architecture

- nabd : daemon qui gère le lapin (i/o, chorégraphies)
- nabclockd : daemon pour le service horloge
- nabsurprised : daemon pour le service surprises
- nabtaichid : daemon pour le service taichi
- nabmastodond : daemon pour le service mastodon

# Protocole nadb

nabd est un serveur TCP/IP et s'interface ainsi avec les daemons des services. Il écoute sur le port 10543.
Chaque paquet est sur une ligne (CRLF), encodée en JSON. Chaque paquet comprend un slot "type".

## Paquets `state`

Indication de l'état du lapin. Ce paquet est envoyé lors de la connexion et lors de tout changement d'état.

Émetteur: nabd

- `{"type":"state","state":state}`

Le slot `"state"` peut être :
- `"asleep"` : le lapin dort ;
- `"idle"` : le lapin est éveillé et affiche les infos ;
- `"interactive"` : le lapin est en mode interactif ;
- `"playing"` : le lapin joue une commande.

## Paquets `info`

Modification de l'animation visuelle du lapin, c'est-à-dire ce qu'il affiche au repos (mode `"idle"`).

Émetteurs: services

- `{"type":"info","request_id":request_id,"info_id":info_id,"animation":animation}`

Le slot `"request_id"`est optionnel et est retourné dans la réponse.

Le slot `"info_id"`, requis, indique l'identification de l'info. C'est cette séquence qui est modifiée. `info_id` est une chaîne.

Le slot `"animation"`, optionnel, indique l'animation visuelle. S'il est absent, l'info est supprimée. S'il est présent, c'est un objet:

`{"tempo":tempo, "colors":colors}`

`tempo` est TBD.
`colors` est une liste pour les couleurs des leds :

`{"left":color,"center":color,"right":color,"bottom":color,"nose":color}`

Tous les slots sont optionnels (`{}` = toutes les leds sont éteintes). `color` est TBD.

## Paquets `ears`

Modification de la position des oreilles au repos (mode `"idle"`). La position des oreilles en mode interactif peut être modifiée avec un paquet `"command"` via une chorégraphie. Le paquet de type `"ears"` est conçu pour le service mariage d'oreilles.

Émetteurs: services

- `{"type":"ears","request_id":request_id,"left":left_ear,"right":right_ear}`

Le slot `"request_id"`est optionnel et est retourné dans la réponse.

Les slots `"left"` et `"right"` sont optionnels (un seul est requis), et `left_ear` comme `right_ear` sont des entiers représentant la position.

## Paquets `command`

Commande à exécuter par le lapin.

Émetteurs: services

- `{"type":"command","request_id":request_id,"sequence":sequence,"expiration":expiration_date,"cancelable":cancelable}`

Le slot `"request_id"` est optionnel et est retourné dans la réponse.

Le slot `"expiration"` est optionnel et indique la date d'expiration de la commande. La commande est jouée quand le lapin est disponible (pas endormi, pas en train de faire autre chose) et si la date d'expiration n'est pas atteinte.

Le slot `"sequence"` est requis et `sequence` est une liste d'éléments du type :

`{"audio":audio_list,"choregraphy":choregraphy}`

Les slots `"audio"` et `"choregraphy"` sont optionnels.

`audio_list` est une liste de sons à jouer sous la forme de chemins vers des fichiers mp3 ou des URLs pour du streaming.

`choregraphy` est ou bien le nom d'une chorégraphie prédéfinie ("streaming") ou bien une définition dans un langage de chorégraphie TBD. La chorégraphie est jouée pendant la lecture des différents fichiers audios de la liste.
On peut avoir une même chorégraphie pendant 3 fichiers audios (signature, message, signature), ou des chorégraphies différentes par fichier audio.

Le slot `"cancelable"` est optionnel. Par défaut, la commande sera annulée par un click sur le bouton. Si `cancelable` est `false`, la commande n'est pas annulée par le bouton (le service doit gérer le bouton).

## Paquets `cancel`

Annule une commande en cours d'exécution (ou programmée).

Émetteurs: services

- `{"type":"cancel","request_id":request_id}`

Le slot `"request_id"` est requis et correspond au slot `"request_id"` de la commande passée. Ne fonctionne que pour les commandes, pas pour les autres paquets.

## Paquets `wakeup`

Réveille le lapin.

Émetteurs: services

- `{"type":"wakeup","request_id":request_id}`

Le slot `"request_id"`est optionnel et est retourné dans la réponse.

## Paquets `sleep`

Endort le lapin. Le lapin s'endort dès que toutes les commandes sont exécutées et qu'il est en mode `"idle"`.

Émetteurs: services

- `{"type":"sleep","request_id":request_id}`

Le slot `"request_id"`est optionnel et est retourné dans la réponse.

## Paquets `mode`

Émetteurs: services

Change le mode pour un service donné.

- `{"type":"mode","request_id":request_id,"mode":mode,"events":events}`

Le slot `"mode"` peut être:
- `"idle"`
- `"interactive"`

Le slot `"events"`, optionnel, est une liste avec:
- `"button"`
- `"ears"`

Pour le mode `"idle"`, si `"events"` n'est pas précisé, cela est équivalent à la liste vide : le service ne reçoit aucun événement. Si `"button"` ou `"ears" ` sont précisés, le service reçoit les événements correspondants lorsque le lapin est éveillé et n'est pas en mode interactif avec un autre service. Par défaut, le mode est `"idle"`, sans événements.

Dans le mode `"interactif"`, le service prend la main sur le lapin et reçoit les événéments précisés. Le lapin cesse d'afficher les infos. Un seul service peut être en mode interactif. Si non précisé, le service reçoit tous les événements. Les autres services ne reçoivent pas les événements, le lapin ne joue pas les commmandes et ne s'endort pas. Le mode interactif s'achève lorsque le service envoie un paquet `"mode"` avec le mode `"idle"` (ou lorsque la connexion est rompue).

## Paquets `ears_event`

Émetteur: nabd

Signifie aux services que les oreilles ont été bougées. Envoyé après calcul des positions (?). Est envoyé aux services qui demandent ce type d'événements (mode idle/interactif).

- `{"type":"ears_event","left":ear_left,"right":ear_right}`

## Paquets `button_event`

Émetteur: nabd

Signifie aux services que le bouton a été appuyé. Est envoyé aux services qui demandent ce type d'événements (mode idle/interactif).

- `{"type":"button_event","event":event}`

Le slot `"event"` peut être:
- `"down"`
- `"up"`
- `"click"`
- `"doubleclick"`

## Paquets `response`

Émetteur: nabd

Réponse de nabd à un paquet d'un service.

- `{"type":"response","request_id":request_id,"status":"ok"}`
- `{"type":"response","request_id":request_id,"status":"canceled"}`
- `{"type":"response","request_id":request_id,"status":"expired"}`
- `{"type":"response","request_id":request_id,"status":"error","class":class,"message":message}`

Le statut `"ok"` signifie que l'info a été ajoutée ou que la commande a été exécutée ou le mode changé. Dans le cas d'une commande, cette réponse est envoyée lorsque la commande est terminée. Idem pour le paquet `"sleep"`. Le slot `"request_id"`, s'il est présent, reprend l'id fourni dans la requête.

Le statut `"canceled"` signifie que l'utilisateur a annulé la commande avec le bouton.

Le statut `"expired"` signifie que la commande est expirée.

Le statut `"error"` signifie une erreur dans le protocole. `class` et `message` sont des chaînes.

Dépendances
===========

* python 3.7
* pytest (pour Travis)
