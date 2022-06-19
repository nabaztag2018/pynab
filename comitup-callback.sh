#!/usr/bin/env bash

if [ "$1" == "CONNECTED" ]; then
	sudo systemctl restart nabairqualityd
	sudo systemctl restart nabweatherd
	echo '{"type":"command","sequence":[{"choreography":"nabd/vert.chor"}]}' | nc -4 -w 5 -v localhost 10543
elif [ "$1" == "HOTSPOT" ]; then
	echo '{"type":"command","sequence":[{"choreography":"nabd/rouge.chor"}]}' | nc -4 -w 5 -v localhost 10543
elif [ "$1" == "CONNECTING" ]; then
	echo '{"type":"command","sequence":[{"choreography":"nabd/orange.chor"}]}' | nc -4 -w 5 -v localhost 10543
fi
