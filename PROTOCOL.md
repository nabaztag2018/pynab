# Protocole nadb
- [Protocole nadb](#protocole-nadb)
  - [Introduction](#introduction)
  - [Examples](#examples)
    - [Console interactive](#console-interactive)
    - [Envoyer un ensemble de commandes](#envoyer-un-ensemble-de-commandes)
  - [Paquets `state`](#paquets-state)
  - [Paquets `info`](#paquets-info)
  - [Paquets `ears`](#paquets-ears)
  - [Paquets `command`](#paquets-command)
  - [Paquets `message`](#paquets-message)
  - [Paquets `cancel`](#paquets-cancel)
  - [Paquets `wakeup`](#paquets-wakeup)
  - [Paquets `sleep`](#paquets-sleep)
  - [Paquets `mode`](#paquets-mode)
  - [Paquets `asr_event`](#paquets-asrevent)
  - [Paquets `ears_event`](#paquets-earsevent)
  - [Paquets `button_event`](#paquets-buttonevent)
  - [Paquets `response`](#paquets-response)
  - [Paquets `rfid_write`](#paquets-rfid_write)
  - [Paquets `gestalt`, `test` et `config-update`](#paquets-gestalt-test-et-config-update)

## Introduction

nabd est un serveur TCP/IP et s'interface ainsi avec les daemons des services. Il écoute sur le port 10543.
Chaque paquet est sur une ligne (CRLF), encodée en JSON. Chaque paquet comprend un slot "type".

## Examples

Pour pouvoir vous-même interagir avec le lapin en lui envoyant de tels paquets, il faut avoir activé SSH pour pouvoir vous connecter en ligne de commande (pour des raisons de sécurité, le traffic sur le port du protocole est limité à 127.0.0.1/localhost: accès local depuis le lapin).

### Console interactive

Une fois connecté au lapin, il suffit de lancer la commande suivante pour voir le statut du lapin et lui envoyer une commande en la tapant (validée par un retour à la ligne):
```
 nc -4 -v localhost 10543
```

Un simple Ctrl+C permet de fermer l'utilitaire 'nc'.

### Envoyer un ensemble de commandes

Si vous voulez préparer un ensemble d'actions au préalable (afin de faire une notification, une chorégraphie, juste pour rire...), il suffit de créer un fichier texte contenant une commande par ligne:
```
 {"type":"ears", "left": 10, "right": 15}
 {"type":"ears", "left": 5, "right": 0}
```

Ensuite, ce fichier de paquets peut-être envoyé au processus nabd pour être appliqué:
```
cat mes_commandes.json | nc -4 -w 5 -v localhost 10543
```

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

`tempo` est en ms.
`colors` est une liste pour les couleurs des leds :

`{"left":color,"center":color,"right":color}`

Tous les slots sont optionnels (`{}` = toutes les leds sont éteintes).
`color` peut être :
-  un nombre de 0 à 15 représentant une valeur dans la palette originale (0 = noir, 15 = orange)
-  un texte représentant la couleur au format HTML ('#' suivi de 3 octets en hexa) ou symbolique

## Paquets `ears`

Modification de la position des oreilles au repos (mode `"idle"`). La position des oreilles en mode interactif peut être modifiée avec un paquet `"command"` via une chorégraphie. Le paquet de type `"ears"` est conçu pour le service mariage d'oreilles.

Émetteurs: services

- `{"type":"ears","request_id":request_id,"left":left_ear,"right":right_ear,"event":boolean}`

Le slot `"request_id"` est optionnel et est retourné dans la réponse.

Les slots `"left"` et `"right"` sont optionnels (un seul est requis), et `left_ear` comme `right_ear` sont des entiers représentant la position.

Le slot `"event"` est optionnel. Il permet de stimuler le service mariage d'oreilles en envoyant un tel paquet au lapin local, sans avoir à bouger ses oreilles à la main
(si `"event"` est `true`, nabd simule un paquet `ears_event` avec la nouvelle position des oreilles).

## Paquets `command`

Commande à exécuter par le lapin.

Émetteurs: services

- `{"type":"command","request_id":request_id,"sequence":sequence,"expiration":expiration_date,"cancelable":cancelable}`

Le slot `"request_id"` est optionnel et est retourné dans la réponse.

Le slot `"expiration"` est optionnel et indique la date d'expiration de la commande. La commande est jouée quand le lapin est disponible (pas endormi, pas en train de faire autre chose) et si la date d'expiration n'est pas atteinte.

Le slot `"sequence"` est requis et `sequence` est une [liste] d'éléments du type :

`{"audio":audio_list,"choreography":choreography}`

Les slots `"audio"` et `"choreography"` sont optionnels.

`audio_list` est une [liste] de sons à jouer.

Chaque son peut être :

- une liste de ressources, séparées par des ";", la première trouvée est celle qui sera jouée.
Chaque ressource est un chemin vers un son tel que `"nabmastodon/communion.wav"`. L'algorithme essaie d'abord dans le sous-répertoire de chaque application correspondant à la langue actuelle du lapin (`"sounds/fr_FR"`) puis dans le répertoire `"sounds"`, les applications dans l'ordre de `"settings.py"`. Si la ressource termine par `"*"` ou `"*.suffixe"`, le son est choisi au hasard dans les éléments du répertoire correspondant.

`choreography` peut être :
- une liste de ressources vers les chorégraphies sur le même mécanisme que les sons, dans les répertoires `choreographies` des différentes applications.
- `"urn:x-chor:streaming"` pour la chorégraphie de streaming avec palette aléatoire.
- `"urn:x-chor:streaming:N"` pour la chorégraphie de streaming avec palette N.
- `"data:application/x-nabaztag-mtl-choreography;base64,<BASE64>"` pour une chorégraphie fournie en Base64

La chorégraphie est jouée pendant la lecture des différents fichiers audios de la liste et est interrompue à la fin de l'audio.
Si aucun son n'est joué, la chorégraphie est jouée jusqu'au bout.
Si la même chorégraphie est indiquée pour les différentes séquences, elle n'est pas interrompue.

Le slot `"cancelable"` est optionnel. Par défaut, la commande sera annulée par un click sur le bouton. Si `cancelable` est `false`, la commande n'est pas annulée par le bouton (le service doit gérer le bouton).

## Paquets `message`

Messages à faire diffuser par le lapin.

Émetteurs: services

- `{"type":"message","request_id":request_id,"signature":signature,"body":body,"cancelable":cancelable}`

Le slot `"request_id"` est optionnel et est retourné dans la réponse.

Le slot `"expiration"` est optionnel et indique la date d'expiration de la commande. La commande est jouée quand le lapin est disponible (pas endormi, pas en train de faire autre chose) et si la date d'expiration n'est pas atteinte.

Le slot `"signature"` est optionnel et est du type :

`{"audio":audio_list,"choreography":choreography}`

Le slot `"body"` est requis et est une [liste] d'éléments du type :

`{"audio":audio_list,"choreography":choreography}`

Les slots `"audio"` et `"choreography"` sont optionnels.

`audio_list` est une liste de sons à jouer, comme pour les paquets `"command"`.
`choreography` est une chorégraphie, comme pour les paquets `"command"`. Cependant, si la chorégraphie n'est pas précisée, alors c'est la chorégraphie de streaming qui est utilisée.

La signature est jouée en premier, suivi du corps du message, puis la signature est rejouée.

Le slot `"cancelable"` est optionnel. Par défaut, la commande sera annulée par un clic sur le bouton. Si `cancelable` est `false`, la commande n'est pas annulée par le bouton (le service doit gérer le bouton).

## Paquets `cancel`

Annule une commande en cours d'exécution (ou programmée).

Émetteurs: services

- `{"type":"cancel","request_id":request_id}`

Le slot `"request_id"` est requis et correspond au slot `"request_id"` de la commande passée. Ne fonctionne que pour les commandes et les messages, pas pour les autres paquets.

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
- `"asr"`
- `"button"`
- `"ears"`

Pour le mode `"idle"`, si `"events"` n'est pas précisé, cela est équivalent à la liste vide: le service ne reçoit aucun événement. Si `"asr"`, `"button"` ou `"ears" ` sont précisés, le service reçoit les événements correspondants lorsque le lapin est éveillé et n'est pas en mode `"interactive"` avec un autre service. Par défaut, le mode est `"idle"`, sans événements.

Dans le mode `"interactive"`, le service prend la main sur le lapin et reçoit les événéments précisés. Le lapin cesse d'afficher les infos. Un seul service peut être en mode interactif. Si non précisé, le service reçoit tous les événements. Les autres services ne reçoivent pas les événements, le lapin ne joue pas les commmandes et ne s'endort pas. Le mode interactif s'achève lorsque le service envoie un paquet `"mode"` avec le mode `"idle"` (ou lorsque la connexion est rompue).

## Paquets `asr_event`

Émetteur: nabd

Signifie aux services qu'une commande vocale a été comprise.
Le slot "nlu" contient le détail de la commande comprise, à partir du moteur de NLU.
En particulier, le slot "intent" contient l'intention détectée.

`{'type': 'asr_event', 'nlu': {'intent': intent}}`

## Paquets `ears_event`

Émetteur: nabd

Signifie aux services que les oreilles ont été bougées.
En mode `"idle"`, nabd calcule la position en lançant une détection et envoie aux services (pour le mariage d'oreilles).
Le paquet a alors cette forme :
- `{"type":"ears_event","left":ear_left,"right":ear_right}`

En mode `"interactive"`, nabd envoie le fait que l'oreille a bougé.

Le paquet a alors cette forme :
- `{"type":"ears_event","ear": ear}`

## Paquets `button_event`

Émetteur: nabd

Signifie aux services que le bouton a été appuyé. Est envoyé aux services qui demandent ce type d'événements (mode `"idle"`/`"interactive"`).

- `{"type":"button_event","event":event}`

Le slot `"event"` peut être:
- `"down"`
- `"up"`
- `"click"`
- `"double_click"`
- `"click_and_hold"`

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

## Paquets `rfid_write`

Utilisés en interne pour la configuration des tags RFID.

## Paquets `gestalt`, `test` et `config-update`

Utilisés en interne pour la communication entre le site web et nabd.

