#!/usr/bin/env bash
echo "Start All realm daemons..."
screen -d -S alignak_broker -m bash -c "alignak-broker -c /usr/local/etc/alignak/daemons/brokerd.ini"
screen -d -S alignak_poller -m bash -c "alignak-poller -c /usr/local/etc/alignak/daemons/pollerd.ini"
screen -d -S alignak_scheduler -m bash -c "alignak-scheduler -c /usr/local/etc/alignak/daemons/schedulerd.ini"
screen -d -S alignak_receiver -m bash -c "alignak-receiver -c /usr/local/etc/alignak/daemons/receiverd.ini"
screen -d -S alignak_reactionner -m bash -c "alignak-reactionner -c /usr/local/etc/alignak/daemons/reactionnerd.ini"
sleep 1
echo "Start Alignak arbiter..."
screen -d -S alignak_arbiter -m bash -c "alignak-arbiter -c /usr/local/etc/alignak/daemons/arbiterd.ini -a /usr/local/etc/alignak/alignak.cfg"