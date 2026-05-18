import paramiko
import os
import sys
import json
import io

# Asegurar salida UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ruta de configuración
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def get_ssh_client(node_name="vps2"):
    config_all = load_config()
    
    # Compatibilidad con config antiguo y nuevo
    if 'nodes' in config_all:
        if node_name not in config_all['nodes']:
            # Fallback al primer nodo si el especificado no existe
            node_name = list(config_all['nodes'].keys())[0]
        node = config_all['nodes'][node_name]
    else:
        node = config_all['vps']
        node_name = "vps"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    key_path = node.get('key_path')
    try:
        if key_path and os.path.exists(key_path):
            ssh.connect(node['host'], port=node.get('port', 22), username=node['user'], key_filename=key_path, timeout=10)
        else:
            password = node.get('password')
            if password == "same_as_pcb":
                password = config_all['nodes']['pcb']['password']
            ssh.connect(node['host'], port=node.get('port', 22), username=node['user'], password=password, timeout=10)
        return ssh, node_name
    except Exception as e:
        print(f"❌ Error conectando a {node_name}: {e}")
        sys.exit(1)

def upload_file(local_path, remote_path, node_name="vps2"):
    print(f"[BRIDGE-{node_name.upper()}] Subiendo {local_path} -> {remote_path}...")
    ssh, _ = get_ssh_client(node_name)
    sftp = ssh.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    ssh.close()
    return "✅ Archivo subido con éxito."

def download_file(remote_path, local_path, node_name="vps2"):
    print(f"[BRIDGE-{node_name.upper()}] Descargando {remote_path} -> {local_path}...")
    ssh, _ = get_ssh_client(node_name)
    sftp = ssh.open_sftp()
    sftp.get(remote_path, local_path)
    sftp.close()
    ssh.close()
    return "✅ Archivo descargado con éxito."

def execute_command(command, node_name="vps2"):
    ssh, name = get_ssh_client(node_name)
    print(f"[BRIDGE-{name.upper()}] Ejecutando: {command}")
    stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)
    
    # Inyectar password solo si el comando contiene 'sudo'
    if 'sudo' in command:
        config_all = load_config()
        if 'nodes' in config_all and name in config_all['nodes']:
            node = config_all['nodes'][name]
            password = node.get('password')
            if password:
                if password == "same_as_pcb": password = config_all['nodes']['pcb']['password']
                stdin.write(password + '\n')
                stdin.flush()

    output = stdout.read().decode('utf-8')
    error = stderr.read().decode('utf-8')
    ssh.close()
    
    if error and not output:
        return f"ERROR:\n{error}"
    return output

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Uso: python vps_bridge.py [nodo] <comando|upload|download> ...")
        sys.exit(1)

    # Determinar si el primer argumento es un nombre de nodo
    config = load_config()
    target_node = "vps2" # Default
    if args[0] in config.get('nodes', {}):
        target_node = args[0]
        args = args[1:]

    if not args:
        print(f"Error: No se especificó acción para el nodo {target_node}")
        sys.exit(1)

    if args[0] == "upload" and len(args) == 3:
        print(upload_file(args[1], args[2], target_node))
    elif args[0] == "download" and len(args) == 3:
        print(download_file(args[1], args[2], target_node))
    else:
        print("\n" + "="*40)
        print(execute_command(" ".join(args), target_node))
        print("="*40)
