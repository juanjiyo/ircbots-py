import paramiko
import time

print('Conectando a PC B...')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.100.37', port=2222, username='juanjo', password='IRCPASSWORD', timeout=5)

print('Subiendo iabot.py (MiLeNiUm)...')
sftp = ssh.open_sftp()
sftp.put('bots/milenium/iabot.py', '/home/juanjo/ircbots/bots/milenium/iabot.py')
sftp.close()

print('Reiniciando proceso milenium...')
ssh.exec_command('screen -X -S milenium quit')
time.sleep(2)
ssh.exec_command('screen -dmS milenium bash -c "cd /home/juanjo/ircbots/bots/milenium && python3 -u iabot.py >> /tmp/milenium.log 2>&1"')
time.sleep(2)

print('Verificando proceso...')
_, stdout, _ = ssh.exec_command('ps aux | grep iabot.py | grep -v grep')
print(stdout.read().decode())
ssh.close()
print('Despliegue de MiLeNiUm completado.')
