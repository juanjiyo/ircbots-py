import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.100.37", port=2222, username="juanjo", password="IRCPASSWORD", timeout=5)

_, stdout, _ = ssh.exec_command("ps aux | grep -E 'iabot|falkian' | grep -v grep")
output = stdout.read().decode().strip()
print(f"Processes on PC B:\n{output}")

ssh.close()
