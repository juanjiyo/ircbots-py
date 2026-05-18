import sys

file_path = "/home/irc/eggdrop/scripts/BlackHoroscopeES.tcl"
with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# 1. Corregir TLS
content = content.replace('::tls::socket -tls1 1', '::tls::socket -autoservername 1')

# 2. Corregir User-Agent
old_ua = 'http::config -useragent "lynx"'
new_ua = 'http::config -useragent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"'
content = content.replace(old_ua, new_ua)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Parche aplicado con éxito.")
