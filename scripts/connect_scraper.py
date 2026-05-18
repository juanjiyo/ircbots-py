import sys

file_path = "/home/irc/eggdrop/scripts/BlackHoroscopeES.tcl"
with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if 'proc horoscopo:get_data {sign} {' in line:
        new_lines.append(line)
        new_lines.append('        global horoscopo\n')
        new_lines.append('        set sign [string tolower $sign]\n')
        new_lines.append('        if {[string equal -nocase $sign "gminis"]} {set sign "geminis"}\n')
        new_lines.append('        if {[string equal -nocase $sign "cncer"]} {set sign "cancer"}\n')
        new_lines.append('        catch {exec python3 /home/irc/hola_scraper.py $sign} hr\n')
        new_lines.append('        set date [clock format [clock seconds] -format "%d-%m-%Y"]\n')
        new_lines.append('        return [list $date $hr]\n')
        new_lines.append('}\n')
        skip = True
    elif skip and 'proc ' in line:
        new_lines.append(line)
        skip = False
    elif not skip:
        new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("TCL conectado al scraper de Python.")
