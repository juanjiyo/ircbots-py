import paramiko
import sys

def connect_and_execute(command):
    host = '192.168.100.88'
    port = 22
    user = 'usuario'
    password = 'same_as_pcb' # We know from config.json it's IRCPASSWORD
    password = 'IRCPASSWORD'

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=host, port=port, username=user, password=password, timeout=10)
        stdin, stdout, stderr = client.exec_command(command)
        out = stdout.read().decode('utf-8')
        err = stderr.read().decode('utf-8')
        print(out)
        if err:
            print(f"STDERR: {err}")
    except Exception as e:
        print(f"Error connecting or executing: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = " ".join(sys.argv[1:])
        connect_and_execute(cmd)
    else:
        print("Usage: python remote_execute_pca.py <command>")
