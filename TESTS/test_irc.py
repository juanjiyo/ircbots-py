import socket

server = "irc.chatzona.org"
port = 6667
channel = "#Limbo"
nickname = "BeBeSaUrIo"
password = "IRCPASSWORD"

irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

print(f"[*] Conectando a {server}...")
irc.connect((server, port))

irc.send(f"NICK {nickname}\r\n".encode())
irc.send(f"USER {nickname} 0 * :BeBeSaUrIo test\r\n".encode())

while True:
    data = irc.recv(2048).decode("utf-8", errors="ignore")
    if not data:
        break

    print(data)

    if data.startswith("PING"):
        irc.send(f"PONG {data.split()[1]}\r\n".encode())
        print("[!] PONG enviado.")

    if "001" in data:
        irc.send(f"PRIVMSG NICK IDENTIFY {password}\r\n".encode())
        print(f"[*] Identificado como {nickname}")
        irc.send(f"JOIN {channel}\r\n".encode())
        print(f"[*] Entrando a {channel}...")
