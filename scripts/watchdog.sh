#!/bin/bash
# Watchdog para bots (KaBoT, Heimdall, Futbot y BotGPT)
# Ejecutar cada 5 min via cron del usuario irc
LOGFILE=/home/irc/watchdog.log
DT=$(date '+%Y-%m-%d %H:%M:%S')

# --- KaBoT (Eggdrop) ---
if ! pgrep -f 'eggdrop eggdrop.conf' > /dev/null 2>&1; then
  echo "[$DT] KaBoT caido, reiniciando..." >> $LOGFILE
  cd /home/irc/eggdrop && ./eggdrop eggdrop.conf
  echo "[$DT] KaBoT reiniciado." >> $LOGFILE
fi

# --- Heimdall (Eggdrop) ---
if ! pgrep -f 'heimdall eggdrop.conf' > /dev/null 2>&1; then
  echo "[$DT] Heimdall caido, reiniciando..." >> $LOGFILE
  cd /home/irc/heimdall && ./heimdall eggdrop.conf
  echo "[$DT] Heimdall reiniciado." >> $LOGFILE
fi

# --- Futbot (Python) ---
if ! pgrep -f 'python3 futbot.py' > /dev/null 2>&1; then
  echo "[$DT] Futbot caido, reiniciando..." >> $LOGFILE
  cd /home/irc/futbot && nohup python3 futbot.py > futbot.log 2>&1 &
  echo "[$DT] Futbot reiniciado." >> $LOGFILE
fi

# --- BotGPT (Python) ---
if ! pgrep -f 'python3 botgpt.py' > /dev/null 2>&1; then
  echo "[$DT] BotGPT caido, reiniciando..." >> $LOGFILE
  cd /home/irc/gemini && nohup python3 botgpt.py > gemini.log 2>&1 &
  echo "[$DT] BotGPT reiniciado." >> $LOGFILE
fi
