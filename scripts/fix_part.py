import sys

file_path = "/home/irc/eggdrop/scripts/publico.tcl"
with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if 'proc do_part {' in line:
        new_lines.append(line)
        new_lines.append('  set chan1 [lindex [split $text " "] 0]\n')
        new_lines.append('  if {$chan1 == ""} { set chan1 $chan }\n')
        new_lines.append('  if {![validchan $chan1]} {\n')
        new_lines.append('    putmsg $chan "Ese canal no existe en mi base de datos."\n')
        new_lines.append('    return 1\n')
        new_lines.append('  }\n')
        new_lines.append('  putlog "Parting $chan1 ordered by $nick"\n')
        new_lines.append('  putserv "PRIVMSG $chan :Saliendo de $chan1 a peticion de $nick"\n')
        new_lines.append('  channel remove $chan1\n')
        new_lines.append('  return 1\n')
        new_lines.append('}\n')
        skip = True
    elif skip and 'proc ' in line: # Encontró la siguiente función
        new_lines.append(line)
        skip = False
    elif not skip:
        new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Función do_part corregida.")
