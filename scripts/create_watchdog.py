#!/usr/bin/env python3
"""Crea watchdog.sh y configura cron en la VPS remota."""
import paramiko, sys

WATCHDOG_SH = r"""#!/bin/bash
# Watchdog para bots Eggdrop (KaBoT + Heimdall)
# Ejecutar cada 5 min via cron del usuario irc
LOGFILE=/home/irc/watchdog.log
DT=$(date '+%Y-%m-%d %H:%M:%S')

# --- KaBoT ---
if ! pgrep -f 'eggdrop eggdrop.conf' > /dev/null 2>&1; then
  echo "[$DT] KaBoT caido, reiniciando..." >> $LOGFILE
  cd /home/irc/eggdrop && ./eggdrop eggdrop.conf
  echo "[$DT] KaBoT reiniciado." >> $LOGFILE
fi

# --- Heimdall ---
if ! pgrep -f 'heimdall eggdrop.conf' > /dev/null 2>&1; then
  echo "[$DT] Heimdall caido, reiniciando..." >> $LOGFILE
  cd /home/irc/heimdall && ./heimdall eggdrop.conf
  echo "[$DT] Heimdall reiniciado." >> $LOGFILE
fi
"""

CRON_LINE = "*/5 * * * * /home/irc/watchdog.sh > /dev/null 2>&1"

def main():
    import json, os
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    with open(config_path) as f:
        cfg = json.load(f)['vps']

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.Ed25519Key.from_private_key_file(cfg['key_path'])
    ssh.connect(cfg['host'], username=cfg['user'], pkey=key, timeout=10)

    # 1. Subir watchdog.sh
    sftp = ssh.open_sftp()
    with sftp.file("/home/irc/watchdog.sh", "w") as f:
        f.write(WATCHDOG_SH)
    sftp.chmod("/home/irc/watchdog.sh", 0o755)
    sftp.close()
    print("[OK] watchdog.sh subido")

    # 2. Configurar cron (solo si no existe ya)
    stdin, stdout, stderr = ssh.exec_command("crontab -l 2>/dev/null")
    current_cron = stdout.read().decode()

    if "watchdog.sh" not in current_cron:
        new_cron = current_cron.rstrip("\n") + "\n" + CRON_LINE + "\n"
        stdin, stdout, stderr = ssh.exec_command(f'echo "{new_cron}" | crontab -')
        err = stderr.read().decode()
        if err:
            print(f"[ERROR] crontab: {err}")
        else:
            print("[OK] Cron configurado: cada 5 minutos")
    else:
        print("[INFO] Cron ya existia, no se modifica")

    # 3. Verificar
    stdin, stdout, stderr = ssh.exec_command("crontab -l && echo '---' && cat /home/irc/watchdog.sh")
    print(stdout.read().decode())

    ssh.close()

if __name__ == "__main__":
    main()
