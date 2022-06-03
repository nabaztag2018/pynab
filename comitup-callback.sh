#!/usr/bin/env bash

if [ "$1" == "CONNECTED" ]; then
	sudo systemctl restart nabairqualityd
	sudo systemctl restart nabweatherd
fi
