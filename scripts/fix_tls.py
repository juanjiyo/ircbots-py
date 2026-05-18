import sys

file_path = "/home/irc/eggdrop/scripts/BlackHoroscopeES.tcl"
with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Corregir la llamada a tls::socket para que sea compatible
# Probamos con una sintaxis más estándar para versiones antiguas/específicas
old_register = 'http::register https 443 [list ::tls::socket -autoservername 1]'
new_register = 'http::register https 443 ::tls::socket'
# También nos aseguramos de que tls esté bien configurado globalmente si es posible, 
# pero por ahora volvemos a lo básico que no da error de argumentos.

content = content.replace(old_register, new_register)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Registro de TLS corregido.")
