#!/bin/bash
daemon=$1
mkdir -p /run
echo $$ > /run/${daemon}.pid
pid=
send_signal() {
    printf "POST /containers/docker_${daemon}_1/kill?signal=SIGUSR1 HTTP/1.1\r\nHost: localhost\r\n\r\n" | nc -q 0 -U /var/run/docker.sock
}
trap send_signal USR1
while :
do
    sleep infinity &
    pid=$!
    wait $!
    [[ $pid ]] && kill "$pid"
    pid=
done
