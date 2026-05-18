#!/bin/bash
# Script para levantar los bots KaBoT y Heimdall
echo "Levantando KaBoT..."
cd /home/irc/eggdrop && ./eggdrop eggdrop.conf
sleep 2
echo "Levantando Heimdall..."
cd /home/irc/heimdall && ./heimdall eggdrop.conf
echo "Bots lanzados."
