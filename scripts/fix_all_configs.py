import os

files = ['/home/irc/eggdrop/eggdrop.conf', '/home/irc/heimdall/eggdrop.conf']

for f in files:
    if os.path.exists(f):
        with open(f, 'r') as file:
            lines = file.readlines()
        
        new_lines = []
        has_python = False
        
        # Primero, limpiar cualquier linea de loadmodule python mal escrita o duplicada
        for l in lines:
            if 'loadmodule python' in l:
                if not has_python:
                    new_lines.append('loadmodule python\n')
                    has_python = True
                continue
            new_lines.append(l)
            
        # Si no estaba, añadirla antes de DNS
        if not has_python:
            final_lines = []
            for l in new_lines:
                if '#### DNS MODULE ####' in l:
                    final_lines.append('loadmodule python\n\n')
                    has_python = True
                final_lines.append(l)
            new_lines = final_lines
            
        with open(f, 'w') as file:
            file.writelines(new_lines)
        print(f"Reparado: {f}")

print("Proceso de reparacion completado.")
