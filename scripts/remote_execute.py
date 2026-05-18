import paramiko
import sys

def connect_and_execute(command):
    host = '192.168.100.37'
    port = 2222
    user = 'juanjo'
    password = 'IRCPASSWORD'

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=host, port=port, username=user, password=password, timeout=10)
        # Execute with sudo if the command needs it, otherwise just run
        # This script runs the command directly
        stdin, stdout, stderr = client.exec_command(command, get_pty=True)
        # Automatically provide password if sudo asks for it
        stdin.write(password + '\n')
        stdin.flush()
        
        out = stdout.read().decode('utf-8')
        print(out)
    except Exception as e:
        print(f"Error connecting or executing: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = " ".join(sys.argv[1:])
        connect_and_execute(cmd)
    else:
        print("Usage: python remote_execute.py <command>")
