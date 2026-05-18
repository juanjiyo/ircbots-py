import os
import sys
import time
import subprocess
import json
import glob
import random
from datetime import datetime

class Stats:
    def __init__(self):
        base = os.path.join(os.path.dirname(__file__), "..", "..", "stats_engine")
        self.logs_dir = os.path.join(base, "logs")
        self.reports_dir = os.path.join(base, "reports")
        self.pipes_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "mircstats", "Pipes")
        if not os.path.exists(self.pipes_dir):
            self.pipes_dir = os.path.join(base, "Pipes")
        self.pisg_dir = os.path.join(base, "pisg-0.73")
        self.pisg_path = os.path.join(self.pisg_dir, "pisg")
        self.cfg_path = os.path.join(base, "pisg.cfg")
        self.stats_file = os.path.join(base, "quick_stats.json")

        for d in [self.logs_dir, self.reports_dir]:
            if not os.path.exists(d):
                os.makedirs(d)

    def _check_config(self, channel):
        if not os.path.exists(self.cfg_path):
            chan_clean = channel.lower().replace("#", "")
            cfg_lines = []
            for f in sorted(os.listdir(self.logs_dir)):
                if f.startswith(chan_clean) and f.endswith(".log"):
                    cfg_lines.append(
                        f'<channel="{channel}">\n'
                        f'  Logfile="{self.logs_dir}/{f}"\n'
                        f'  Format="mIRC"\n'
                        f'  Network="ChatHispano"\n'
                        f'  OutputFile="{self.reports_dir}/{chan_clean}.html"\n'
                        f'</channel>\n'
                    )
            try:
                with open(self.cfg_path, "w") as f:
                    f.write("# pisg.cfg generado por MiLeNiUm\n")
                    f.writelines(cfg_lines)
            except Exception as e:
                print(f"[Stats] Error writing cfg: {e}")

    def _compilar_stats(self, channel):
        chan_clean = channel.lower().replace("#", "")
        archivos = sorted(glob.glob(os.path.join(self.logs_dir, f"{chan_clean}.*.log")))
        conteo = {}
        ultima_frase = {}
        frases_usuario = {}
        for archivo in archivos:
            try:
                with open(archivo, "r", encoding="utf-8") as f:
                    for line in f:
                        m = line.strip()
                        if "> " in m:
                            parts = m.split("> ", 1)
                            nick_part = parts[0].split("<")[-1]
                            nick = nick_part
                            msg = parts[1].strip()
                            conteo[nick] = conteo.get(nick, 0) + 1
                            ultima_frase[nick] = msg
                            if nick not in frases_usuario:
                                frases_usuario[nick] = []
                            if len(frases_usuario[nick]) < 20:
                                frases_usuario[nick].append(msg)
            except Exception:
                continue

        total = sum(conteo.values())
        ranking = sorted(conteo.items(), key=lambda x: x[1], reverse=True)
        stats = {
            "total": total,
            "dias": len(archivos),
            "ranking": {n: c for n, c in ranking},
            "ultima_frase": ultima_frase,
            "frases": {n: fs for n, fs in frases_usuario.items()},
            "timestamp": time.time(),
        }
        try:
            todos = {}
            if os.path.exists(self.stats_file):
                with open(self.stats_file, "r") as f:
                    todos = json.load(f)
            todos[chan_clean] = stats
            with open(self.stats_file, "w") as f:
                json.dump(todos, f, indent=2)
        except Exception as e:
            print(f"[Stats] Error saving quick stats: {e}")

        return conteo, total, ranking

    def _cargar_stats(self, channel):
        chan_clean = channel.lower().replace("#", "")
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, "r") as f:
                    todos = json.load(f)
                return todos.get(chan_clean)
            except Exception:
                pass
        return None

    def log_message(self, channel, nick, message):
        self._write_log(channel, f"<{nick}> {message}")

    def log_action(self, channel, nick, message):
        self._write_log(channel, f"* {nick} {message}")

    def _write_log(self, channel, line):
        try:
            date_str = datetime.now().strftime("%d-%m-%Y")
            time_str = datetime.now().strftime("%H:%M")
            filename = f"{channel.lower().replace('#', '')}.{date_str}.log"
            filepath = os.path.join(self.logs_dir, filename)
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"[{time_str}] {line}\n")
        except Exception as e:
            print(f"[Stats] Error writing log: {e}")

    def _quotes_from_file(self, channel, nick, max_q=10):
        chan_clean = channel.lower().replace("#", "")
        archivos = sorted(glob.glob(os.path.join(self.logs_dir, f"{chan_clean}.*.log")))
        quotes = []
        nick_lower = nick.lower()
        for archivo in reversed(archivos):
            try:
                with open(archivo, "r", encoding="utf-8") as f:
                    for line in f:
                        m = line.strip()
                        if f"<{nick_lower}>" in m.lower():
                            parts = m.split("> ", 1)
                            if len(parts) > 1:
                                ts = parts[0].split("[")[-1].split("]")[0] if "[" in parts[0] else ""
                                msg = parts[1].strip()
                                quotes.append((ts, msg))
                                if len(quotes) >= max_q:
                                    break
                if len(quotes) >= max_q:
                    break
            except Exception:
                continue
        return quotes

    def generar_html(self, channel, user, excluir_nicks=None):
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "stats_engine"))
            from generator import MircStatsGenerator
            gen = MircStatsGenerator(self.logs_dir, self.reports_dir, pipes_dir=self.pipes_dir)
            html_path = gen.generate(channel, excluir_nicks=excluir_nicks)
            if html_path:
                return [f"\x0303\u2714\ufe0f Estad\u00edsticas completas generadas por \x02{user}\x02.",
                        f"\x0312\ud83d\udcc4 Visite las estad\u00edsticas en \x0302{html_path}\x0F"]
            return [f"\x0310\u26a0\ufe0f No hay suficientes datos para generar estad\u00edsticas."]
        except Exception as e:
            return [f"\x0304\u274c Error generando HTML: {e}"]

    def obtener_lineas(self, channel, target_user):
        stats = self._cargar_stats(channel)
        if stats:
            lineas = stats.get("ranking", {}).get(target_user, 0)
            total = stats["total"]
            if lineas == 0:
                return [f"\x0310Lo siento \x02{target_user}\x02, no has escrito ninguna l\u00ednea en el canal.\x0F"]
            pct = round((lineas / total) * 100, 3) if total else 0
            ranking = sorted(stats["ranking"].items(), key=lambda x: x[1], reverse=True)
            pos = next((i + 1 for i, (n, _) in enumerate(ranking) if n == target_user), 0)

            # Random quote
            frases = stats.get("frases", {})
            frases_nick = frases.get(target_user, [])
            if frases_nick:
                fq = random.choice(frases_nick)
                quote_str = f" .L\u00ednea aleatoria: ( {fq[:80]} )"
            else:
                qts = self._quotes_from_file(channel, target_user, 15)
                if qts:
                    ts, msg = random.choice(qts)
                    quote_str = f" .L\u00ednea aleatoria: ( {ts} ) \"{msg[:60]}\""
                else:
                    quote_str = ""

            orden = f"{pos}\u00ba posici\u00f3n"
            return [
                f"\x0312{target_user}\x0F ha escrito \x0304{self.formatear_numero(lineas)} l\u00edneas\x0F, "
                f"el \x0304{pct}%\x0F de las l\u00edneas del canal y est\u00e1 en la \x0304{orden}\x0F"
                f"{quote_str}"
                f" .Si quieres el \x02Ranking\x02 entero escribe : \x02!top5 LINEAS\x02"
            ]

        conteo, total, ranking = self._compilar_stats(channel)
        if not conteo:
            return [f"\x0310Lo siento \x02{target_user}\x02, no has escrito ninguna l\u00ednea en el canal.\x0F"]
        lineas = conteo.get(target_user, 0)
        if lineas == 0:
            return [f"\x0310Lo siento \x02{target_user}\x02, no has escrito ninguna l\u00ednea en el canal.\x0F"]
        pct = round((lineas / total) * 100, 3)
        pos = next((i + 1 for i, (n, _) in enumerate(ranking) if n == target_user), 0)
        orden = f"{pos}\u00ba posici\u00f3n"
        return [
            f"\x0312{target_user}\x0F ha escrito \x0304{self.formatear_numero(lineas)} l\u00edneas\x0F, "
            f"el \x0304{pct}%\x0F de las l\u00edneas del canal y est\u00e1 en la \x0304{orden}\x0F."
        ]

    def comando_top(self, channel, n=10):
        stats = self._cargar_stats(channel)
        conteo = stats["ranking"] if stats else {}
        if not conteo:
            conteo, _, _ = self._compilar_stats(channel)
        if not conteo:
            return ["\x0310A\u00fan no hay registros de actividad para generar un Ranking.\x0F"]
        ranking = sorted(conteo.items(), key=lambda x: x[1], reverse=True)[:n]
        partes = []
        for i, (nick, cnt) in enumerate(ranking):
            if i == 0:
                partes.append(f"\x02\x0304#{i+1} {nick}\x0F (\x0304{self.formatear_numero(cnt)}\x0F)")
            else:
                partes.append(f"\x02\x0304#{i+1}\x0F {nick} (\x0304{self.formatear_numero(cnt)}\x0F)")
        return [f"Top {n} en {channel}: {' | '.join(partes)}"]

    def generar_reporte(self, channel, user, bypass_cooldown=False):
        self._check_config(channel)
        
        # Check cooldown
        if not bypass_cooldown:
            stats = self._cargar_stats(channel)
            if stats and "timestamp" in stats:
                transcurrido = time.time() - stats["timestamp"]
                if transcurrido < 14400:
                    restante = 14400 - transcurrido
                    return [f"\x0310Quedan \x02{self.formatear_tiempo(restante)}\x02 para poder actualizar las stats.\x0F"]

        respuestas = [f"\x0310Realización de estadísticas en curso. Solicitadas por: \x02{user}\x02.\x0F"]
        try:
            subprocess.Popen(
                ["perl", self.pisg_path, "-co", self.cfg_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            conteo, total, ranking = self._compilar_stats(channel)

            # Today's top
            hoy = self._analizar_logs_hoy(channel)
            if hoy:
                top_hoy = sorted(hoy.items(), key=lambda x: x[1], reverse=True)
                top_hoy_strs = []
                for i, (n, c) in enumerate(top_hoy[:5]):
                    if i == 0:
                        top_hoy_strs.append(f"\x02\x0304{n}\x0F (\x0304{self.formatear_numero(c)}\x0F)")
                    else:
                        top_hoy_strs.append(f"{n} ({self.formatear_numero(c)})")
                respuestas.append(
                    f"\x0312Resumen de estadísticas\x0F - Los que más han escrito hoy -> "
                    f"{', '.join(top_hoy_strs)}"
                )


            chan_clean = channel.lower().replace("#", "")
            respuestas.append(f"\x0303\u2705 Estad\u00edsticas actualizadas por \x02{user}\x02.")
            return respuestas
        except Exception as e:
            return [f"\x0304\u274c Error al procesar estad\u00edsticas: {e}"]

    def actualizar_stats(self, channel, user, bypass_cooldown=False):
        return self.generar_reporte(channel, user, bypass_cooldown)

    def formatear_tiempo(self, segundos):
        horas = int(segundos // 3600)
        minutos = int((segundos % 3600) // 60)
        segs = int(segundos % 60)
        res = []
        if horas > 0: res.append(f"{horas}hrs")
        if minutos > 0: res.append(f"{minutos}mins")
        if segs > 0: res.append(f"{segs}secs")
        return " ".join(res)

    def formatear_numero(self, n):
        return f"{n:,}".replace(",", ".")

    def _analizar_logs_hoy(self, channel):
        chan_clean = channel.lower().replace("#", "")
        date_str = datetime.now().strftime("%d-%m-%Y")
        filepath = os.path.join(self.logs_dir, f"{chan_clean}.{date_str}.log")
        conteo = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        if "> " in line:
                            nick = line.split("> ", 1)[0].split("<")[-1]
                            conteo[nick] = conteo.get(nick, 0) + 1
            except Exception:
                pass
        return conteo

    # VIP system
    VIP_FILE = os.path.join(os.path.dirname(__file__), "..", "datos", "vip_users.json")

    def _cargar_vip(self) -> dict:
        try:
            with open(self.VIP_FILE, "r") as f:
                return json.load(f)
        except:
            return {}

    def _guardar_vip(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self.VIP_FILE), exist_ok=True)
        with open(self.VIP_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def comando_vip(self, nick: str, args: str) -> list:
        partes = args.strip().split()
        sub = partes[0].lower() if partes else ""
        vips = self._cargar_vip()

        if not sub:
            return [f"\x0306!vip add <nick> [nivel] [canal]\x0F  \x0306!vip del <nick>\x0F  \x0306!vip list\x0F"]

        if sub == "add":
            target = partes[1].lower() if len(partes) > 1 else ""
            if not target:
                return [f"\x0304Uso: !vip add <nick> [nivel] [canal]\x0F"]
            nivel = int(partes[2]) if len(partes) > 2 and partes[2].isdigit() else 1
            canal = partes[3] if len(partes) > 3 else ""
            if nivel < 1 or nivel > 5:
                return [f"\x0304El nivel debe ser 1-5\x0F"]
            vips[target] = {"nivel": nivel, "canal": canal}
            self._guardar_vip(vips)
            return [f"\x0310 {target} es VIP nivel {nivel}{f' en {canal}' if canal else ''}\x0F"]

        if sub == "del":
            target = partes[1].lower() if len(partes) > 1 else ""
            if not target or target not in vips:
                return [f"\x0304{nick} no es VIP\x0F"]
            del vips[target]
            self._guardar_vip(vips)
            return [f"\x0310 {target} ya no es VIP\x0F"]

        if sub == "list":
            if not vips:
                return ["\x0306No hay usuarios VIP\x0F"]
            lines = [f"\x0306VIPs ({len(vips)}):\x0F"]
            for u, d in vips.items():
                nivel = d.get("nivel", 1)
                canal = f" en {d['canal']}" if d.get("canal") else ""
                lines.append(f"  \x0312{u}\x0F (nivel {nivel}){canal}")
            return lines

        return [f"\x0304Subcomando no valido: usa add/del/list\x0F"]
