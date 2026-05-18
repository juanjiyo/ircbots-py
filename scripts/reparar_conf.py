import os

files = ['/home/irc/eggdrop/eggdrop.conf', '/home/irc/heimdall/eggdrop.conf']

for filepath in files:
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Corregir la línea pegada
        new_content = content.replace('windows-1250"pysource', 'windows-1250"\npysource')
        
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Reparado: {filepath}")
    else:
        print(f"No encontrado: {filepath}")
