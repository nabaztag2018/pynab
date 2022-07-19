#!/usr/bin/env bash

if [ "$1" == "CONNECTED" ]; then
	systemctl is-active --quiet nabairqualityd && sudo systemctl kill -s SIGUSR1 nabairqualityd
	systemctl is-active --quiet nabweatherd && sudo systemctl kill -s SIGUSR1 nabweatherd
	systemctl is-enabled --quiet nabblockly && sudo systemctl start nabblockly
	echo '{"type":"command","sequence":[{"choreography":"nabd/vert.chor"}]}' | nc -4 -w 5 -v localhost 10543
elif [ "$1" == "HOTSPOT" ]; then
	systemctl is-enabled --quiet nabblockly && sudo systemctl stop nabblockly
	echo '{"type":"command","sequence":[{"choreography":"nabd/rouge.chor"}]}' | nc -4 -w 5 -v localhost 10543
elif [ "$1" == "CONNECTING" ]; then
	echo '{"type":"command","sequence":[{"choreography":"nabd/orange.chor"}]}' | nc -4 -w 5 -v localhost 10543
fi
