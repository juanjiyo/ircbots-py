import os
import re
import random
import glob
from datetime import datetime, timedelta
from collections import defaultdict
from html import escape

MS_BG       = "#F8F9FC"
MS_PRIMARY  = "#3B5998"
MS_HEADER   = "#3B5998"
MS_HEADER_FG = "#F8F9FC"
MS_ROW_EVEN = "#FFFFFF"
MS_ROW_ODD  = "#DFE3EE"

TIME_PIPES = ["pipe1.png", "pipe2.png", "pipe3.png", "pipe4.png"]
TIME_PIPES_V = ["pipe1v.png", "pipe2v.png", "pipe3v.png", "pipe4v.png"]
TIME_LABELS = ["0-6", "6-12", "12-18", "18-24"]
TIME_TITLES = ["Los m\u00e1s nocturnos", "Madrugadores", "Tarde", "Nocturnas y Nocturnos"]
WEEKDAY_ES = ["Lunes", "Martes", "Mi\u00e9rcoles", "Jueves", "Viernes", "S\u00e1bado", "Domingo"]

MONTH_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


class MircStatsGenerator:
    def __init__(self, logs_dir, output_dir, pipes_dir=None):
        self.logs_dir = logs_dir
        self.output_dir = output_dir
        self.pipes_dir = pipes_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        # Copy pipe images to output dir
        if pipes_dir and os.path.isdir(pipes_dir):
            import shutil
            for f in os.listdir(pipes_dir):
                if f.endswith(".png"):
                    shutil.copy2(os.path.join(pipes_dir, f), os.path.join(output_dir, f))

    def generate(self, channel, excluir_nicks=None):
        chan_clean = channel.lower().replace("#", "")
        excluir = set(n.lower() for n in (excluir_nicks or []))
        archivos = sorted(glob.glob(os.path.join(self.logs_dir, f"{chan_clean}.*.log")))
        if not archivos:
            return None
        datos = self._parse_logs(archivos, excluir)
        if not datos["total"]:
            return None

        pages = [
            (f"{chan_clean}.html",         self._page1(channel, chan_clean, datos)),
            (f"{chan_clean}_p2.html",      self._page2(channel, chan_clean, datos)),
            (f"{chan_clean}_p3.html",      self._page3(channel, chan_clean, datos)),
            (f"{chan_clean}_p4.html",      self._page4(channel, chan_clean, datos)),
        ]
        for filename, html in pages:
            with open(os.path.join(self.output_dir, filename), "w", encoding="utf-8") as f:
                f.write(html)
        return os.path.join(self.output_dir, pages[0][0])

    # ── Helpers ────────────────────────────────────────────────────────

    def _pipe(self, name, w, h, extra=""):
        return f'<img src="{name}" width="{w}" height="{h}"{extra}>'

    def _css(self):
        return f"""body {{ text-align: center; font-family: "Verdana", Arial, sans-serif; background-color: {MS_BG}; color: {MS_PRIMARY}; font-size: 12px }}
h1 {{ font-family: "Comic Sans MS"; color: {MS_PRIMARY}; font-size: 26px; font-style: italic; font-weight: bold; margin: 4px }}
h3 {{ font-family: "Comic Sans MS"; color: {MS_PRIMARY}; font-size: 20px; font-style: italic; font-weight: bold; margin: 3px }}
h4 {{ font-family: "Comic Sans MS"; color: #000000; font-size: 16px; font-style: italic; font-weight: bold; margin: 2px }}
h5 {{ font-family: "Comic Sans MS"; color: {MS_PRIMARY}; font-size: 16px; font-style: italic; font-weight: bold; margin: 2px }}
table {{ border: 0px ; padding: 0px; border-spacing: 1px }}
img {{ border-width: 0px; }}
.ttxt {{ border: 0px; padding: 2px }}
.tgr,  .tinv {{ border: 0px }}
.tadj {{ border-style: none; border-collapse: collapse }}
.tadj td {{ border: 0px none; padding: 0px }}
.txt1 {{ font-family: "Verdana"; color: {MS_PRIMARY}; font-size: 12px; text-align: left }}
.txt2 {{ font-family: "Verdana"; color: #000000; font-size: 12px; text-align: left }}
.t1 {{ font-family: "Verdana"; color: {MS_PRIMARY}; font-size: 12px; text-align: left; font-weight: bold }}
.t2 {{ font-family: "Verdana"; color: #000000; font-size: 12px; text-align: left; font-style: normal }}
.t5 {{ font-family:"Arial"; color:#000000; font-size:12px; text-align:left; font-weight:normal; font-style: italic }}
.t6 {{ font-family:"Verdana"; color:#000000; font-size:10px; text-align:right; font-style: normal; white-space:nowrap; }}
.tal {{ text-align: left }}
.tar {{ text-align: right }}
.tac {{ text-align: center }}
.s1 {{ font-family: "Arial"; color: #000000; font-size: 8px; vertical-align: bottom; text-align: center  }}
.s2 {{ font-family: "Arial"; color: {MS_PRIMARY}; font-size: 9px; vertical-align: bottom; text-align: center ; border: 0px }}
.s3 {{ font-family: "Arial"; color: #000000; font-size: 9px; vertical-align: bottom; text-align: center }}
.s4 {{ font-family: "Verdana"; color: #000000; font-size: 10px; text-align: left }}
.s5 {{ font-family: "Verdana"; color: #000000; font-size: 10px; text-align: left; border:0px }}
.sq {{ font-style: italic }}
.win {{ font-weight: bold }}
.toc {{ font-family: "Comic Sans MS"; color: #000000; font-size: 16px; font-style: italic; font-weight: bold; margin: 2px }}
.ra {{ font-family: "Arial"; color: {MS_PRIMARY}; font-size: 32px; text-align: center; border-style: solid; border-width: 4px; border-color: #ffffff #000000 #000000 #ffffff; }}
.rn {{ font-family:"Verdana"; color:{MS_PRIMARY};font-size:16px; text-align:left;font-weight:bold; font-style:normal; }}
.rb {{ border-style:solid;border-width:3px 0px; border-color:{MS_BG}; color:{MS_PRIMARY}}}
.box {{ Border: 1px solid {MS_PRIMARY} }}
.ac {{ font-family: "Verdana", Arial, sans-serif; color:#000000; font-size: 10px; vertical-align: middle; text-align: center }}
.am {{ vertical-align: top; Border: 1px solid {MS_PRIMARY} }}
.cr {{ background-color: {MS_BG}; padding: 2px; border-style: outset; border-width: 2px; font-family: Arial, sans-serif; color: {MS_PRIMARY}; font-size: 12px; vertical-align: middle; text-align: left }}
.ca {{ background-color: {MS_BG} }}
.cb {{ background-color: {MS_BG} }}
.cc {{ background-color: {MS_BG} }}
.cbg {{ background-color: {MS_BG} }}
.cn {{ background-color: {MS_ROW_ODD} }}
.cd {{ background-color: {MS_ROW_ODD} }}
.ce {{ background-color: {MS_ROW_ODD} }}
.cf {{ background-color: {MS_ROW_ODD} }}
.cns {{ background-color: #E4E7F0 }}
.cas {{ background-color: {MS_BG} }}
.cbs {{ background-color: {MS_BG} }}
.ccs {{ background-color: {MS_BG} }}
.cds {{ background-color: #E4E7F0 }}
.ces {{ background-color: #E4E7F0 }}
.cfs {{ background-color: #E4E7F0 }}
.cda {{ background-color: {MS_ROW_ODD} }}
.cdb {{ background-color: {MS_ROW_ODD} }}
.cdc {{ background-color: {MS_ROW_ODD} }}
.cea {{ background-color: {MS_ROW_ODD} }}
.ceb {{ background-color: {MS_ROW_ODD} }}
.cec {{ background-color: {MS_ROW_ODD} }}
.cfa {{ background-color: {MS_ROW_ODD} }}
.cfb {{ background-color: {MS_ROW_ODD} }}
.cfc {{ background-color: {MS_ROW_ODD} }}
.cs0 {{ background-color: #A0A0A0 }}
.cs1 {{ background-color: #FF0000 }}
.cs2 {{ background-color: #FFFF00 }}
.cs3 {{ background-color: #00FF00 }}
.cs4 {{ background-color: #00FFFF }}
.cs5 {{ background-color: #0000FF }}
.cs1a {{ background-color: #FF7F00 }}
.cs2a {{ background-color: #7FFF00 }}
.cs3a {{ background-color: #00FF7F }}
.cs4a {{ background-color: #007FFF }}
A {{ color: {MS_PRIMARY} }}
-->"""

    def _sh(self, title, subtitle=""):
        if subtitle:
            return f'<br><table width="95%" cellspacing=0 cellpadding=1 border=0><tr><td bgcolor="{MS_HEADER}"><center>' \
                   f'<font color="{MS_HEADER_FG}" size="4" face="Comic Sans MS"><b><i>{title}</i></b></font>' \
                   f'<br><font color="{MS_HEADER_FG}" size="2" face="Comic Sans MS"><b><i>{subtitle}</i></b></font>' \
                   f'</center></td></tr></table><br>'
        return f'<br><table width="95%" cellspacing=0 cellpadding=1 border=0><tr><td bgcolor="{MS_HEADER}"><center>' \
               f'<font color="{MS_HEADER_FG}" size="4" face="Comic Sans MS"><b><i>{title}</i></b></font>' \
               f'</center></td></tr></table><br>'

    def _nav(self, chan_clean, current):
        pages = [
            (f"{chan_clean}.html", "1. Actividad del Canal"),
            (f"{chan_clean}_p2.html", "2. Estad\u00edsticas Detalladas"),
            (f"{chan_clean}_p3.html", "3. Estad\u00edsticas Usuarios"),
            (f"{chan_clean}_p4.html", "4. Curiosidades del Canal"),
        ]
        parts = []
        for href, label in pages:
            if href == current:
                parts.append(f"<b>{label}</b>")
            else:
                parts.append(f'<a href="{href}" target="_self">{label}</a>')
        return " | ".join(parts)

    def _header_html(self, channel, chan_clean, page_file, d=None):
        e = escape
        nav = self._nav(chan_clean, page_file)
        if d:
            dias = (d["end"] - d["start"]).days + 1 if d["start"] and d["end"] else 0
            inicio = self._fmt_date_es(d["start"])
            fin = self._fmt_date_es(d["end"])
            summary = f'<span class=txt2>Actividad desde el {inicio} hasta el {fin}<br>\nEn {dias} d\u00edas un total de {d["users_count"]} personas han visitado el {e(channel)}<br>\n<br></span>\n'
        else:
            summary = ""

        return f"""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<!-- This page was created on {datetime.now().strftime("%-d.%-m.%Y %H:%M")} with MiLeNiUm Stats Engine -->
<html><head>
<meta http-equiv="Content-Type" content="text/html;charset=UTF-8">
<meta http-equiv="Expires" content="0">
<meta http-equiv="Last-Modified" content="0">
<meta http-equiv="Cache-Control" content="no-cache, mustrevalidate">
<meta http-equiv="Pragma" content="no-cache">
<title>Estad\u00edsticas del {e(channel)} creadas por MiLeNiUm Stats Engine</title>
<style type="text/css">
<!--
{self._css()}
</style>
</head>
<body><center>
<!-- mircstatsheader.txt: Add here your own header html code! -->
<div class="gradientBg">
<table class="sitio">
  <tr>
    <td class="sitioContenido">
      <center>
<br>
<br><table width="95%" cellspacing=0 cellpadding=1 border=0><tr><td bgcolor="{MS_HEADER}"><center>
<font color="{MS_HEADER_FG}" size="5" face="Comic Sans MS"><b><i>Estad\u00edsticas del canal {e(channel)} generadas por MiLeNiUm Stats Engine</i></b></font>
<br><font color="{MS_HEADER_FG}" size="2" face="Comic Sans MS"><b><i>Generado el {datetime.now().strftime("%d/%m/%Y %H:%M")}</i></b></font>
</center></td></tr></table><br>
{summary}{nav}
<br><br>"""

    def _legend(self):
        html = '<table border=0 class=txt1><tr>'
        for i in range(4):
            html += f'<td class=tinv>{self._pipe(TIME_PIPES[i], 30, 15, " align=top")} Horas {TIME_LABELS[i]}</td><td class=tinv width=20></td>'
        html += '</tr></table><br>'
        return html

    def _footer_html(self, chan_clean):
        nav = self._nav(chan_clean, "")
        return f"""
{nav}
<br><br>
<!-- mircstatsheader.txt: Add here your own footer html code! -->
      </center>
    </td>
  </tr>
</table>
</div>
<br>
<table class=cr><tr><td class=tinv>
<a href="https://pisg.github.io/" target="_top">MiLeNiUm Stats Engine</a> &copy; Inspirado en mIRCStats v1.25
</td></tr></table><br>
</center></body></html>"""

    def _fmt(self, n):
        s = f"{n:,.0f}".replace(",", ".")
        return s

    def _fmt_date(self, dt):
        return dt.strftime("%d/%m/%Y") if dt else "N/A"

    def _fmt_date_es(self, dt):
        return f"{WEEKDAY_ES[dt.weekday()]} {dt.day}.{dt.month}.{dt.year}" if dt else "N/A"

    def _fmt_date_short(self, dt):
        return dt.strftime("%d.%m.") if dt else ""

    def _fmt_time(self, hora, minuto):
        return f"{hora:02d}:{minuto:02d}"

    def _bar_h(self, pipe, w, h, title=""):
        t = f' title="{title}"' if title else ""
        return self._pipe(pipe, w, h, t)

    def _bar_h_block(self, block, count, max_count, width=150, height=15):
        if max_count <= 0:
            return ""
        w = max(1, int(count / max_count * width))
        return self._pipe(TIME_PIPES[block], w, height, f' title="{count}"')

    # ── Parse ──────────────────────────────────────────────────────────

    def _parse_logs(self, archivos, excluir):
        line_re = re.compile(r"\[(\d+):(\d+)\]\s+<([^>]+)>\s+(.*)")
        action_re = re.compile(r"\[\d+:\d+\]\s+\*\s+(\S+)\s+(.*)")
        url_re = re.compile(r'https?://[^\s<>\"\']+')

        d = {
            "total": 0, "words_total": 0, "days": len(archivos),
            "start": None, "end": None,
            "by_day": defaultdict(int), "by_day_block": defaultdict(lambda: defaultdict(int)),
            "by_hour": defaultdict(int), "by_weekday": defaultdict(int),
            "by_week_block": defaultdict(lambda: defaultdict(int)),
            "users": defaultdict(lambda: {
                "lines": 0, "words": 0, "chars": 0, "actions": 0,
                "questions": 0, "exclamations": 0, "uppercase": 0,
                "first": None, "last": None, "quotes": [],
                "block": defaultdict(int), "weekday": defaultdict(int),
                "hours": defaultdict(int), "active_days": set(),
                "urls": [], "unique_words": defaultdict(int), "line_lengths": [],
                "consecutive_streak": 0, "max_consecutive": 0,
                "self_talk": 0,
            }),
            "word_freq": defaultdict(int), "word_last_by": {}, "word_first_by": {},
            "urls_all": [], "url_first_by": {},
            "pairs": defaultdict(int),
            "pairs_block": [defaultdict(int) for _ in range(4)],
            "topic_changes": [],
            "by_week": defaultdict(int),
        }

        prev_nick = None
        for archivo in archivos:
            fecha_str = os.path.basename(archivo).split(".")[1]
            try:
                fecha = datetime.strptime(fecha_str, "%d-%m-%Y")
            except ValueError:
                try:
                    fecha = datetime.strptime(fecha_str, "%Y-%m-%d")
                except ValueError:
                    continue
            if d["start"] is None or fecha < d["start"]:
                d["start"] = fecha
            if d["end"] is None or fecha > d["end"]:
                d["end"] = fecha
            try:
                with open(archivo, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()

                iso_week = fecha.isocalendar()[1]
                d["by_week"][(fecha.year, iso_week)] += 0

                for raw_line in lines:
                    line = raw_line.strip()
                    if not line:
                        continue
                    m = line_re.match(line)
                    if not m:
                        ma = action_re.match(line)
                        if ma:
                            nick = ma.group(1).lower()
                            if nick not in excluir:
                                d["users"][nick]["actions"] += 1
                        continue
                    hora = int(m.group(1))
                    minuto = int(m.group(2))
                    nick = m.group(3).lower()
                    msg = m.group(4)
                    if nick in excluir:
                        continue
                    block = hora // 6
                    d["total"] += 1
                    d["by_day"][fecha] += 1
                    d["by_hour"][hora] += 1
                    d["by_weekday"][fecha.weekday()] += 1
                    d["by_day_block"][fecha][block] += 1
                    d["by_week"][(fecha.year, iso_week)] += 1

                    u = d["users"][nick]
                    u["lines"] += 1
                    u["words"] += len(msg.split())
                    u["chars"] += len(msg)
                    u["line_lengths"].append(len(msg))
                    if u["first"] is None:
                        u["first"] = (fecha, hora, minuto)
                    u["last"] = (fecha, hora, minuto)
                    if len(u["quotes"]) < 50:
                        u["quotes"].append((fecha, hora, minuto, msg))
                    if "?" in msg:
                        u["questions"] += 1
                    if "!" in msg:
                        u["exclamations"] += 1
                    if msg == msg.upper() and len(msg) > 3:
                        u["uppercase"] += 1
                    u["block"][block] += 1
                    u["weekday"][fecha.weekday()] += 1
                    u["hours"][hora] += 1
                    u["active_days"].add(fecha)

                    if prev_nick == nick:
                        u["consecutive_streak"] += 1
                        if u["consecutive_streak"] > u["max_consecutive"]:
                            u["max_consecutive"] = u["consecutive_streak"]
                    else:
                        u["consecutive_streak"] = 0

                    if prev_nick and prev_nick != nick:
                        pair = tuple(sorted([prev_nick, nick]))
                        d["pairs"][pair] += 1
                        d["pairs_block"][block][pair] += 1
                    prev_nick = nick

                    for url in url_re.findall(msg):
                        d["urls_all"].append((fecha, hora, minuto, nick, url))
                        u["urls"].append(url)
                        if url not in d["url_first_by"]:
                            d["url_first_by"][url] = (nick, fecha, hora, minuto)

                    for w in msg.lower().split():
                        w_clean = re.sub(r'[^\w\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00fc]', '', w)
                        if len(w_clean) > 1:
                            d["word_freq"][w_clean] += 1
                            d["word_last_by"][w_clean] = nick
                            if w_clean not in d["word_first_by"]:
                                d["word_first_by"][w_clean] = (nick, fecha, hora)
                            u["unique_words"][w_clean] += 1
            except Exception:
                continue

        d["words_total"] = sum(u["words"] for u in d["users"].values())
        d["users_count"] = len(d["users"])
        for u in d["users"].values():
            u["rand_quotes"] = random.sample(u["quotes"], min(3, len(u["quotes"]))) if u["quotes"] else []
            u["all_quotes"] = u["quotes"][:]
            avg = sum(u["line_lengths"]) / max(1, len(u["line_lengths"]))
            u["avg_line_len"] = round(avg, 1)

        # Self-talk: also count when a user responds to their own last line
        # This is already tracked via consecutive_streak
        # Additional self-talk: when a user's line is preceded by someone else but the line before that is theirs
        # Skip this for simplicity

        # Topic changes: not in our logs, skip

        return d

    # ── Page 1: Channel Activity ──────────────────────────────────────

    def _page1(self, channel, chan_clean, d):
        e = escape
        ranking = sorted(d["users"].items(), key=lambda x: x[1]["lines"], reverse=True)
        dias = (d["end"] - d["start"]).days + 1 if d["start"] and d["end"] else 0

        html = self._header_html(channel, chan_clean, f"{chan_clean}.html", d)
        html += self._legend()

        # ── Hourly ──
        html += '<a name="hourl"></a>'
        html += self._sh("\u00bfCu\u00e1ndo hablamos?")
        max_h = max(d["by_hour"].values()) if d["by_hour"] else 1
        html += '<table cellspacing=1 cellpadding=0><tr class=s1 valign=bottom>'
        for h in range(24):
            count = d["by_hour"].get(h, 0)
            height = max(1, int(count / max_h * 100))
            pipe = TIME_PIPES[h // 6]
            for _ in range(6):
                html += f'<td class=tgr>{self._pipe(pipe, 2, height)}</td>'
        html += '</tr><tr class=s1>'
        for h in range(24):
            html += f'<td colspan=6 class=s2>{d["by_hour"].get(h, 0)}</td>'
        html += '</tr><tr class=s3>'
        for h in range(24):
            bg_cls = "ca" if h % 2 == 0 else "cd"
            html += f'<td colspan=6 class="{bg_cls}">{h}</td>'
        html += '</tr></table><br>'

        # ── Daily ──
        html += '<a name="dail"></a>'
        html += self._sh("Actividad diaria")
        max_d = max(d["by_day"].values()) if d["by_day"] else 1
        html += '<table cellspacing=1 cellpadding=2><tr class=s1 valign=bottom>'
        for fecha in sorted(d["by_day"].keys()):
            total = d["by_day"][fecha]
            html += '<td class=tgr>'
            html += f'{total}<br>'
            for idx, block in enumerate([3, 2, 1, 0]):
                count = d["by_day_block"][fecha].get(block, 0)
                height = max(1, int(count / max_d * 100))
                html += self._pipe(TIME_PIPES_V[block], 30, height)
                if idx < 3:
                    html += '<br>'
            html += '</td>'
        html += '</tr><tr class=s3>'
        for i, fecha in enumerate(sorted(d["by_day"].keys())):
            bg_cls = "cf" if i % 2 == 0 else "cd"
            html += f'<td class={bg_cls} style="font-size:9px">{fecha.strftime("%-d.%-m.")}</td>'
        html += '</tr></table><br>'

        # ── Activity distribution ──
        html += '<a name="activ"></a>'
        period_str = ""
        if d["start"] and d["end"]:
            period_str = f'{d["start"].strftime("%-m/%Y")} - {d["end"].strftime("%-m/%Y")}'
        html += self._sh("Distribuci\u00f3n de actividad", period_str)
        ranges = [
            (2500, 999999, "cs1", "2500+"), (2000, 2499, "cs1a", "2000..2499"),
            (1500, 1999, "cs2", "1500..1999"), (1000, 1499, "cs2a", "1000..1499"),
            (750, 999, "cs3", "750..999"), (500, 749, "cs3a", "500..749"),
            (250, 499, "cs4", "250..499"), (1, 249, "cs5", "1..249"), (0, 0, "cs0", "0"),
        ]
        daily_vals = list(d["by_day"].values())
        total_days = len(daily_vals)
        html += '<table border=0 cellspacing=1 cellpadding=2 class=t6>'
        html += '<tr class=t1><td class=ca>L\u00edneas por d\u00eda</td><td class=cb>N\u00famero de d\u00edas</td></tr>'
        for lo, hi, css, label in ranges:
            count = sum(1 for v in daily_vals if lo <= v <= hi)
            pct = count / total_days * 100 if total_days else 0
            bar_w = max(1, int(pct / 100 * 300))
            if lo == 0 and hi == 0:
                row_bg = "cd"
                row_bg2 = "ce"
                html += f'<tr><td class={row_bg}><table width="100%" class=t6 style="border:0px;"><tr><td width="17" class="{css} ac">&nbsp;</td><td class=tinv>{label}</td></tr></table></td>'
            else:
                row_bg = "cds" if (lo // 250) % 2 == 0 else "cd"
                row_bg2 = "ces" if (lo // 250) % 2 == 0 else "ce"
                html += f'<tr><td class={row_bg}><table width="100%" class="t6 tinv"><tr><td width="17" class="{css} box">&nbsp;</td><td class=tinv>{label}</td></tr></table></td>'
            html += f'<td class="{row_bg2} tal"> <img src="pipead.png" width="{bar_w}" height=17 class=ac> {count} ({pct:.1f}%) </td></tr>'
        html += '</table><br>'

        # ── Time of day top 10 ──
        html += '<a name="time"></a>'
        html += self._sh("Horas a las que estamos m\u00e1s activos")
        html += '<table cellspacing=1 cellpadding=2 class="t2 tar">'
        html += '<tr class=t1><td class=tinv>&nbsp;</td>'
        for i in range(4):
            html += f'<td class="{"ca" if i%2==0 else "cb"} tac">{TIME_TITLES[i]}<br><span class=t6>(Horas {TIME_LABELS[i]})</span></td>'
        html += '</tr>'
        for rank in range(10):
            html += f'<tr><td class=cns>{rank+1}</td>'
            for block_idx in range(4):
                block_users = sorted(
                    [(nick, u["block"].get(block_idx, 0)) for nick, u in ranking],
                    key=lambda x: x[1], reverse=True
                )
                if rank < len(block_users) and block_users[rank][1] > 0:
                    nick, count = block_users[rank]
                    max_b = max(u["block"].get(block_idx, 0) for _, u in ranking) or 1
                    w = max(1, int(count / max_b * 100))
                    bg_cls = "cds" if rank % 2 == 0 else "cd"
                    html += f'<td class={bg_cls}>{e(nick)} - {count}<br>{self._pipe(TIME_PIPES[block_idx], w, 5)}</td>'
                else:
                    bg_cls = "cds" if rank % 2 == 0 else "cd"
                    html += f'<td class={bg_cls}>&nbsp;</td>'
            html += '</tr>'
        html += '</table><br>'

        html += self._footer_html(chan_clean)
        return html

    # ── Page 2: Detailed Stats ────────────────────────────────────────

    def _page2(self, channel, chan_clean, d):
        e = escape
        ranking = sorted(d["users"].items(), key=lambda x: x[1]["lines"], reverse=True)
        total_users = len(ranking)

        html = self._header_html(channel, chan_clean, f"{chan_clean}_p2.html", d)
        html += self._legend()
        html += '<br><br>'

        # ── Top chatters ──
        html += '<a name="user"></a>'
        html += self._sh(f"Los {total_users} m\u00e1s charlatanes")
        html += '<table border=0 cellspacing=1 cellpadding=2 class=t2>'
        html += '<tr class=t1><td class=tinv>&nbsp;</td><td class=ca> Nick </td>'
        html += '<td class=cb> N\u00famero de l\u00edneas </td>'
        html += '<td colspan=2 class=cc> L\u00ednea aleatoria </td></tr>'
        for i, (nick, u) in enumerate(ranking):
            bg_num = "cns" if i % 2 == 0 else "cn"
            bg_nick = "cds" if i % 2 == 0 else "cd"
            bg_lines = "ces" if i % 2 == 0 else "ce"
            bg_date = "cfs" if i % 2 == 0 else "cf"
            bg_quote = "cfs" if i % 2 == 0 else "cf"

            # Build bar: for each block that has data, show a colored pipe
            max_ub = max(u["block"].values()) if any(u["block"].values()) else 1
            bar_html = ""
            total_bars = 0
            for b in range(4):
                cnt = u["block"].get(b, 0)
                if cnt > 0:
                    w = max(1, int(cnt / max(d["by_hour"].values()) * 100) if max(d["by_hour"].values()) > 0 else 1)
                    w = max(1, int(cnt / max_ub * 84))
                    total_bars += cnt
                    bar_html += self._pipe(TIME_PIPES[b], w, 15, f' title="{cnt}"')

            if not bar_html:
                bar_html = self._pipe(TIME_PIPES[0], 1, 15, ' title="0"')

            quote_html = ""
            if u["rand_quotes"]:
                fq = u["rand_quotes"][0]
                q_text = e(fq[3][:80])
                if len(fq[3]) > 80:
                    q_text += "..."
                quote_html = f'{fq[0].strftime("%-d.%-m.")} {fq[1]:02d}:{fq[2]:02d}'

            # Truncate long quotes in display
            q_display = ""
            if u["rand_quotes"]:
                fq = u["rand_quotes"][0]
                q_text = e(fq[3][:80])
                if len(fq[3]) > 80:
                    q_text += "..."
                q_full = e(fq[3][:200])
                q_display = f'<span class=t5 title="{q_full}">"{q_text}"</span>'
            else:
                q_display = ""

            html += f'<tr><td class="{bg_num} tar">{i+1}</td>'
            html += f'<td class="{bg_nick} win">{e(nick)}</td>'
            html += f'<td class="{bg_lines}">{bar_html} {u["lines"]}</td>'
            html += f'<td class="{bg_date} t6">{quote_html}</td>'
            html += f'<td class="{bg_quote} t5">{q_display}</td></tr>'
        html += '</table><br>'

        # ── Big Numbers ──
        html += '<a name="bign"></a>'
        html += self._sh("\u00a1Datos, quiero datos!")
        html += '<table cellspacing=1 cellpadding=6 width="700" class=t2 style="white-space:nowrap">'

        # Find who has most actions (/me)
        if ranking:
            top_actions = sorted(ranking, key=lambda x: x[1]["actions"], reverse=True)
            if top_actions[0][1]["actions"] > 0:
                nick_a, u_a = top_actions[0]
                html += f'<tr><td class=cd><b>{e(nick_a)}</b> quer\u00eda que todo el mundo supiera lo que hac\u00eda y utiliz\u00f3 el /me {u_a["actions"]} veces.<br>'
                if u_a["all_quotes"]:
                    action_quotes = [q for q in u_a["all_quotes"] if q[3].startswith("\u0001ACTION") or False]
                    # Show a sample
                    sample_q = u_a["all_quotes"][0]
                    html += f'<span class=s4>Como esto:</span><table class=tinv><tr><td width=30 class=tinv>&nbsp;</td><td class=s5>{sample_q[0].strftime("%-d.%-m.")} {sample_q[1]:02d}:{sample_q[2]:02d} * {e(nick_a)} <span class=sq>{e(sample_q[3][:80])}</span><br></td></tr></table>'
                html += '</td></tr>'

            # Most consecutive lines
            top_consec = sorted(ranking, key=lambda x: x[1]["max_consecutive"], reverse=True)
            if top_consec[0][1]["max_consecutive"] >= 5:
                nick_c, u_c = top_consec[0]
                html += f'<tr><td class=cda><b>{e(nick_c)}</b> debe ser autista, escribi\u00f3 m\u00e1s de 5 l\u00edneas seguidas {u_c["max_consecutive"]} veces.<br>'

                # Self-talk
                self_talkers = sorted(ranking, key=lambda x: x[1]["consecutive_streak"], reverse=True)
                if len(self_talkers) > 1:
                    st_nick = self_talkers[0][0] if self_talkers[0][0] != nick_c else (self_talkers[1][0] if len(self_talkers) > 1 else None)
                    if st_nick:
                        st_count = d["users"][st_nick]["consecutive_streak"]
                        html += f'<span class=s4><br>{e(st_nick)} parece que hable con las paredes ya que habl\u00f3 {st_count} veces consigo mismo</span><br>'
                html += '</td></tr>'

            # Most uppercase
            top_up = sorted(ranking, key=lambda x: x[1]["uppercase"], reverse=True)
            if top_up[0][1]["uppercase"] > 0:
                nick_up, u_up = top_up[0]
                html += f'<tr><td class=cdb><b>{e(nick_up)}</b> se qued\u00f3 sin voz, porque escribi\u00f3 {u_up["uppercase"]} l\u00edneas en MAY\u00daSCULAS.<br>'
                if u_up["all_quotes"]:
                    up_q = u_up["all_quotes"][0]
                    html += f'<span class=s4>Como esto:</span><table class=tinv><tr><td width=30 class=tinv>&nbsp;</td><td class=s5>{up_q[0].strftime("%-d.%-m.")} {up_q[1]:02d}:{up_q[2]:02d} &lt;{e(nick_up)}&gt; <span class=sq>{e(up_q[3][:80])}</span><br></td></tr></table>'
                html += '</td></tr>'

            # Longest lines
            top_long = sorted(ranking, key=lambda x: x[1]["avg_line_len"], reverse=True)
            if top_long[0][1]["lines"] >= 5:
                nick_l, u_l = top_long[0]
                avg_chan = round(sum(u["avg_line_len"] * u["lines"] for _, u in ranking) / max(1, d["total"]), 1)
                html += f'<tr><td class=cdc><b>{e(nick_l)}</b> escribi\u00f3 las l\u00edneas m\u00e1s largas, con una media de {u_l["avg_line_len"]} letras por l\u00ednea.<br>'
                html += f'<span class=s4><br>La media del canal {e(channel)} es de {avg_chan} letras por l\u00ednea.</span><br>'
                html += '</td></tr>'

        html += '</table><br>'

        # ── Word stats ──
        html += '<a name="word"></a>'
        html += self._sh(f"Palabras m\u00e1s utilizadas en el {e(channel)}:")
        top_words = sorted(d["word_freq"].items(), key=lambda x: x[1], reverse=True)[:20]
        if top_words:
            html += '<table border=0 cellspacing=1 cellpadding=2 class=t2>'
            html += '<tr class=t1><td class="cn tac">Veces</td>'
            html += '<td class=ca>Palabra</td>'
            html += '<td class=cb>\u00daltima vez por</td>'
            html += '<td class=cc>Fecha</td></tr>'
            for i, (word, count) in enumerate(top_words):
                bg_c = "cns" if i % 2 == 0 else "cn"
                bg_w = "cds" if i % 2 == 0 else "cd"
                bg_l = "ces" if i % 2 == 0 else "ce"
                bg_f = "cfs" if i % 2 == 0 else "cf"
                last = d["word_last_by"].get(word, "?")
                first_info = d["word_first_by"].get(word, ("?", None, None))
                first_date = f'{first_info[1].strftime("%-d.%-m.")} {first_info[2]:02d}:00' if first_info[1] else ""
                html += f'<tr><td class="{bg_c} tac">{count}</td>'
                html += f'<td class="{bg_w} t5">"{e(word)}"</td>'
                html += f'<td class="{bg_l}">{e(last)}</td>'
                html += f'<td class="{bg_f} t6">{first_date}</td></tr>'
            html += '</table><br>'

        # ── Unique words per user ──
        html += '<br><h5>\u00bfInventores de palabras?</h5>'
        unique_per_user = []
        for nick, u in ranking:
            user_unique = [w for w in u["unique_words"] if d["word_freq"].get(w, 0) <= 3]
            if user_unique:
                # Count total uses of these unique words
                total_uses = sum(u["unique_words"][w] for w in user_unique)
                # Pick top 5 by frequency
                top_unique = sorted(user_unique, key=lambda w: u["unique_words"][w], reverse=True)[:5]
                sample_str = ", ".join([f'"{e(w)}"({u["unique_words"][w]})' for w in top_unique])
                unique_per_user.append((nick, total_uses, sample_str))
        if unique_per_user:
            unique_per_user.sort(key=lambda x: x[1], reverse=True)
            html += '<table border=0 cellspacing=1 cellpadding=2 class=t2 style="white-space:nowrap">'
            html += '<tr class=t1><td class="cns tac">Veces</td>'
            html += '<td class=cas>Nick</td>'
            html += '<td class=cbs>Muestra seleccionada aleatoriamente (suma)</td>'
            for i, (nick, count, sample) in enumerate(unique_per_user[:15]):
                bg_n = "cns" if i % 2 == 0 else "cn"
                bg_nick = "cds" if i % 2 == 0 else "cd"
                bg_s = "ces" if i % 2 == 0 else "ce"
                html += f'<tr><td class="{bg_n} tac">{count}</td>'
                html += f'<td class="{bg_nick}">{e(nick)}</td>'
                html += f'<td class="{bg_s} t5">{sample}, ...</td></tr>'
            html += '</table><br>'

        # ── Shared vocabulary pairs ──
        html += '<br><h5>Estos dos hablan con sus propias palabras</h5>'
        # Find pairs that share unique words (words mostly used by them)
        pair_words = defaultdict(list)
        for (n1, n2), _ in sorted(d["pairs"].items(), key=lambda x: x[1], reverse=True)[:20]:
            shared = []
            for w in d["word_freq"]:
                w_users = [u for u, _ in ranking if w in d["users"].get(u, {}).get("unique_words", {}) and d["users"][u]["unique_words"][w] > 0]
                if len(w_users) <= 3 and n1 in w_users and n2 in w_users:
                    total_uses = sum(d["users"][nu]["unique_words"].get(w, 0) for nu in [n1, n2])
                    shared.append((w, total_uses))
            if shared:
                shared.sort(key=lambda x: x[1], reverse=True)
                top_shared = shared[:6]
                sample = ", ".join([f'"{e(w)}"({c})' for w, c in top_shared])
                pair_words[(n1, n2)] = (len(shared), sample)

        if pair_words:
            sorted_pairs = sorted(pair_words.items(), key=lambda x: x[1][0], reverse=True)[:15]
            html += '<table border=0 cellspacing=1 cellpadding=2 class=t2 style="white-space:nowrap">'
            html += '<tr class=t1><td class="cns tac">Veces</td>'
            html += '<td class=cas>Nicks</td>'
            html += '<td class=cbs>Muestra seleccionada aleatoriamente (suma)</td>'
            for i, ((n1, n2), (count, sample)) in enumerate(sorted_pairs):
                bg_n = "cns" if i % 2 == 0 else "cn"
                bg_nick = "cds" if i % 2 == 0 else "cd"
                bg_s = "ces" if i % 2 == 0 else "ce"
                html += f'<tr><td class="{bg_n} tac">{count}</td>'
                html += f'<td class="{bg_nick}">{e(n1)} y {e(n2)}</td>'
                html += f'<td class="{bg_s} t5">{sample}, ...</td></tr>'
            html += '</table><br>'

        # ── Chat pairs by time block ──
        html += '<a name="chat"></a>'
        html += self._sh("Parejas de chat", "Los que m\u00e1s hablan entre s\u00ed")
        html += '<table cellspacing=1 cellpadding=2 class=t2>'
        for block_group in [(0, 1), (2, 3)]:
            b1, b2 = block_group
            html += f'<tr class=t1><td width=200 class=ca colspan=3>Horas {TIME_LABELS[b1]}</td><td width=20 class=tinv>&nbsp;</td><td width=200 class=cb colspan=3>Horas {TIME_LABELS[b2]}</td></tr>'
            # Get top pairs for each block
            pairs_b1 = sorted(d["pairs_block"][b1].items(), key=lambda x: x[1], reverse=True)[:10]
            pairs_b2 = sorted(d["pairs_block"][b2].items(), key=lambda x: x[1], reverse=True)[:10]
            max_b1 = max((c for _, c in pairs_b1), default=1)
            max_b2 = max((c for _, c in pairs_b2), default=1)
            max_rows = max(len(pairs_b1), len(pairs_b2), 1)
            for r in range(max_rows):
                if r == 0:
                    html += '<tr>'
                else:
                    html += '<tr>'
                # Block 1 pair
                if r < len(pairs_b1):
                    (n1, n2), count = pairs_b1[r]
                    bg_rank = "cns" if r % 2 == 0 else "cn"
                    bg_n = "cds" if r % 2 == 0 else "cd"
                    bg_n2 = "ces" if r % 2 == 0 else "ce"
                    bar_w = max(1, int(count / max_b1 * 150))
                    html += f'<td class="{bg_rank} tac" rowspan=2>{r+1}</td>'
                    html += f'<td class="{bg_n} tar"><b>{e(n1)}</b></td><td class="{bg_n2}"><b>{e(n2)}</b></td>'
                    html += f'<td rowspan=2></td>'
                else:
                    html += f'<td class=tinv colspan=3></td><td rowspan=2></td>'

                # Block 2 pair
                if r < len(pairs_b2):
                    (n1, n2), count = pairs_b2[r]
                    bg_rank = "cns" if r % 2 == 0 else "cn"
                    bg_n = "cds" if r % 2 == 0 else "cd"
                    bg_n2 = "ces" if r % 2 == 0 else "ce"
                    bar_w = max(1, int(count / max_b2 * 150))
                    html += f'<td class="{bg_rank} tac" rowspan=2>{r+1}</td>'
                    html += f'<td class="{bg_n} tar"><b>{e(n1)}</b></td><td class="{bg_n2}"><b>{e(n2)}</b></td>'
                else:
                    html += f'<td class=tinv colspan=3></td>'
                html += '</tr><tr>'

                if r < len(pairs_b1):
                    (n1, n2), count = pairs_b1[r]
                    bar_w = max(1, int(count / max_b1 * 150))
                    html += f'<td class=cfs colspan=2>{self._pipe(TIME_PIPES[b1], bar_w, 7)}</td>'
                else:
                    html += '<td class=tinv colspan=2></td>'

                if r < len(pairs_b2):
                    (n1, n2), count = pairs_b2[r]
                    bar_w = max(1, int(count / max_b2 * 150))
                    html += f'<td class=cfs colspan=2>{self._pipe(TIME_PIPES[b2], bar_w, 7)}</td>'
                else:
                    html += '<td class=tinv colspan=2></td>'

                html += '</tr>'
            html += '<tr><td class=tinv colspan=7><br><br></td></tr>'
        html += '</table><br>'

        # ── Long term stats ──
        html += '<a name="long"></a>'
        html += self._sh("Estad\u00edsticas de dos semanas")
        # Group by biweekly periods (every 2 weeks)
        biweekly = defaultdict(int)
        biweekly_labels = []
        if d["start"] and d["end"]:
            cur = d["start"]
            while cur <= d["end"]:
                # Find the Monday of the week
                monday = cur - timedelta(days=cur.weekday())
                period_key = monday.strftime("%-d.%-m.")
                period_end = monday + timedelta(days=13)
                label = f"{monday.strftime('%-d.%-m.')}"
                if period_key not in biweekly_labels:
                    biweekly_labels.append(period_key)
                for fecha, count in d["by_day"].items():
                    if monday <= fecha <= period_end:
                        biweekly[period_key] += count
                cur = period_end + timedelta(days=1)

        if biweekly:
            max_bw = max(biweekly.values()) if biweekly else 1
            html += '<table cellspacing=1 cellpadding=2><tr class=s1 valign=bottom>'
            for label in biweekly_labels:
                count = biweekly.get(label, 0)
                height = max(1, int(count / max_bw * 80))
                html += f'<td class=s2>{count}<br>{self._pipe("pipeltv.png", 28, height)}</td>'
            html += '</tr><tr class=s3>'
            for i, label in enumerate(biweekly_labels):
                bg_cls = "cd" if i % 2 == 0 else "cd"
                html += f'<td class={bg_cls}>{label}</td>'
            html += '</tr></table>'
            # Estimate next period
            last_total = d["total"]
            estimate = int(last_total / max(1, len(biweekly_labels)) * 2)
            html += f'<span class=txt2>N\u00famero total de l\u00edneas: {self._fmt(last_total)}</span><br>'
            html += f'<span class=txt2>Estimaci\u00f3n para esta temporada: {self._fmt(estimate)} l\u00edneas.</span><br><br>'

        html += self._footer_html(chan_clean)
        return html

    # ── Page 3: User Stats ────────────────────────────────────────────

    def _page3(self, channel, chan_clean, d):
        e = escape
        ranking = sorted(d["users"].items(), key=lambda x: x[1]["lines"], reverse=True)

        html = self._header_html(channel, chan_clean, f"{chan_clean}_p3.html", d)
        html += '<br><br>'
        html += self._legend()
        html += '<a name="pers"></a>'
        html += self._sh("Estad\u00edsticas personales")

        for i, (nick, u) in enumerate(ranking):
            if i >= 30:
                break
            pct = round(u["lines"] / d["total"] * 100, 1) if d["total"] else 0
            first = f"{u['first'][0].strftime('%-d.%-m.%y')} {u['first'][1]:02d}:{u['first'][2]:02d}" if u["first"] else "N/A"
            last = f"{u['last'][0].strftime('%-d.%-m.%y')} {u['last'][1]:02d}:{u['last'][2]:02d}" if u["last"] else "N/A"

            # Calculate "today/yesterday" for last message
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if u["last"]:
                last_dt = u["last"][0].replace(hour=u["last"][1], minute=u["last"][2])
                if last_dt >= today:
                    last_display = f'Hoy {u["last"][1]:02d}:{u["last"][2]:02d}'
                elif last_dt >= today - timedelta(days=1):
                    last_display = f'Ayer {u["last"][1]:02d}:{u["last"][2]:02d}'
                else:
                    last_display = f'{u["last"][0].strftime("%-d.%-m.")} {u["last"][1]:02d}:{u["last"][2]:02d}'
            else:
                last_display = "N/A"

            active_days = len(u["active_days"])
            avg_per_day = round(u["lines"] / max(1, active_days))
            q_pct = round(u["questions"] / max(1, u["lines"]) * 100, 1)
            e_pct = round(u["exclamations"] / max(1, u["lines"]) * 100, 1)

            html += f'<table width="90%" class=txt1 cellspacing=0 cellpadding=3 style="border:0px;">'
            html += f'<tr class=t1><td class="ra cd" width=30>{i+1}</td><td class=tinv width=10>&nbsp;</td>'
            html += f'<td colspan=2 class=rb><span class=rn>{e(nick)}</span></td></tr>'
            html += '<tr><td class=tinv colspan=2></td><td class=tinv colspan=2><table class=txt1 style="border:0px;"><tr style="vertical-align:top">'

            # Column 1: last seen
            html += '<td class=ttxt><table style="border:0px;" class=txt1>'
            html += f'<tr><td class=tinv>\u00daltima vez que escribi\u00f3: {last_display}</td></tr>'
            html += '</table></td>'

            # Column 2: stats
            html += '<td class=tinv>&nbsp;</td><td class=ttxt><table class=txt1 style="border:0px;">'
            html += f'<tr><td class=tinv>Visitas: {active_days}</td></tr>'
            html += f'<tr><td class=tinv>l\u00edneas: {u["lines"]}</td></tr>'
            html += f'<tr><td class=tinv>d\u00edas activos: {active_days}/{d["days"]}</td></tr>'
            html += f'<tr><td class=tinv>Media de l\u00edneas por d\u00eda: {avg_per_day}</td></tr>'
            html += f'<tr><td class=tinv>Media de letras por l\u00ednea: {u["avg_line_len"]}</td></tr>'
            html += '</table></td>'

            # Column 3: questions etc
            html += '<td class=tinv>&nbsp;</td><td class=ttxt><table class=txt1 style="border:0px;">'
            html += f'<tr><td class=tinv>Preguntas: {q_pct}%</td></tr>'
            html += f'<tr><td class=tinv>Exclamaciones: {e_pct}%</td></tr>'
            if u["uppercase"] > 0:
                up_pct = round(u["uppercase"] / max(1, u["lines"]) * 100, 1)
                html += f'<tr><td class=tinv>May\u00fasculas: {up_pct}%</td></tr>'
            if u["actions"] > 0:
                html += f'<tr><td class=tinv>N\u00famero de /me: {u["actions"]}</td></tr>'
            html += '</table></td>'
            html += '</tr></table></td></tr>'

            # Activity charts row
            html += '<tr><td class=tinv colspan=2></td><td class=tinv colspan=2>'
            html += '<table style="border:0px;"><tr class=txt2>'
            html += '<td class=ttxt>Actividad semanal</td>'
            html += '<td class=tinv rowspan=2>&nbsp;</td>'
            html += '<td class=ttxt>Actividad por horas</td>'
            html += '<td class=tinv rowspan=2>&nbsp;</td>'
            html += '<td class=ttxt>\u00daltimos d\u00edas</td>'
            html += '<td class=tinv rowspan=2>&nbsp;</td>'
            html += '<td class=ttxt>Habla m\u00e1s con...:</td>'
            html += '</tr>'

            html += '<tr style="vertical-align:bottom">'

            # Weekly activity: per weekday with 4 time blocks
            html += '<td class=ttxt>'
            html += '<table cellspacing=1 cellpadding=0 style="border:0px;"><tr class=s1 valign=bottom>'
            max_wd = max(u["weekday"].values()) if u["weekday"] else 1
            for day in range(7):
                total_day = u["weekday"].get(day, 0)
                html += '<td class=tgr>'
                if total_day > 0:
                    for block in range(4):
                        count_block = sum(1 for q in u.get("all_quotes", []) if q[0].weekday() == day and q[1] // 6 == block)
                        # Approximate from block data
                        total_blocks = sum(u["block"].values()) or 1
                        block_share = u["block"].get(block, 0) / total_blocks if total_blocks > 0 else 0
                        h = max(0, int(total_day * block_share / max_wd * 64))
                        if h > 0:
                            html += self._pipe(TIME_PIPES_V[block], 15, h)
                else:
                    html += self._pipe(TIME_PIPES_V[0], 15, 1)
                html += '</td>'
            html += '</tr><tr class=s3>'
            for day in range(7):
                html += f'<td class=cd>{WEEKDAY_ES[day][0]}</td>'
            html += '</tr></table>'
            html += '</td>'

            # Hourly activity (4 blocks of 6 hours)
            html += '<td class=ttxt>'
            html += '<table cellspacing=1 cellpadding=0 style="border:0px;"><tr class=s1 valign=bottom>'
            max_uh = max(u["hours"].values()) if u["hours"] else 1
            for block in range(4):
                total_block = u["block"].get(block, 0)
                h = max(0, int(total_block / max_uh * 64))
                html += f'<td class=tgr>{self._pipe(TIME_PIPES_V[block], 8, max(1, h))}</td>'
            html += '</tr><tr class=s3>'
            for block in range(4):
                html += f'<td colspan=3 class=cd>{TIME_LABELS[block]}</td>'
            html += '</tr></table>'
            html += '</td>'

            # Last N days activity
            html += '<td class=ttxt>'
            html += '<table cellspacing=1 cellpadding=0 style="border:0px;"><tr class=s1 valign=bottom>'
            last_days = sorted(d["by_day"].keys())[-11:] if len(d["by_day"]) > 11 else sorted(d["by_day"].keys())
            max_ld = max(d["by_day"][fd] for fd in last_days) if last_days else 1
            for fd in last_days:
                total_day = d["by_day"].get(fd, 0)
                html += '<td class=tgr>'
                if total_day > 0:
                    for block in range(4):
                        count_b = d["by_day_block"][fd].get(block, 0)
                        uc = u["block"].get(block, 0)
                        if uc > 0 and count_b > 0:
                            share = total_day / max_ld if max_ld > 0 else 0
                            h = max(0, int(uc / max_uh * 64)) if max_uh > 0 else 0
                            h = max(0, int(count_b / max(d["by_day"][fd], 1) * uc / max(1, u["lines"]) * 64))
                            if h > 0:
                                html += self._pipe(TIME_PIPES_V[block], 8, h)
                else:
                    html += self._pipe(TIME_PIPES_V[0], 8, 1)
                html += '</td>'
            html += '</tr><tr class=s3>'
            for fd in last_days:
                html += f'<td class=cd style="font-size:7px">{fd.strftime("%-d/%-m")}</td>'
            html += '</tr></table>'
            html += '</td>'

            # Chat partners
            html += '<td class=ttxt style="vertical-align:top">'
            user_pairs = [(n2, c) for (n1, n2), c in d["pairs"].items() if n1 == nick] + \
                         [(n1, c) for (n1, n2), c in d["pairs"].items() if n2 == nick]
            user_pairs.sort(key=lambda x: x[1], reverse=True)
            if user_pairs:
                max_up = user_pairs[0][1] if user_pairs else 1
                html += '<table style="border:0px;" class=txt1>'
                for partner, count in user_pairs[:5]:
                    w = max(1, int(count / max_up * 80))
                    html += f'<tr><td class=tinv>{e(partner)}</td><td class=tinv>'
                    for b in range(4):
                        pair_key = tuple(sorted([nick, partner]))
                        pair_block_count = d["pairs_block"][b].get(pair_key, 0)
                        if pair_block_count > 0:
                            pw = max(1, int(pair_block_count / count * 80))
                            html += self._pipe(TIME_PIPES[b], pw, 8)
                    html += '</td></tr>'
                html += '</table>'
            else:
                html += '&nbsp;'
            html += '</td>'

            html += '</tr></table></td></tr>'

            # Last lines
            if u["all_quotes"]:
                html += '<tr><td class=tinv colspan=2></td><td class=tinv colspan=2>'
                html += '<span class=ttxt>Las \u00faltimas l\u00edneas</span><br>'
                html += '<table border=0 cellspacing=1 cellpadding=2 class=t2>'
                last_q = u["all_quotes"][-10:]
                for j, fq in enumerate(last_q):
                    q_date = f'{fq[0].strftime("%-d.%-m.")} {fq[1]:02d}:{fq[2]:02d}'
                    q_msg = e(fq[3][:120])
                    bg1 = "ces" if j % 2 == 0 else "ce"
                    bg2 = "cfs" if j % 2 == 0 else "cf"
                    html += f'<tr><td class="{bg1} t6">{q_date}</td><td class="{bg2}" width="100%">&lt;{e(nick)}&gt; <span class=t5>{q_msg}</span></td></tr>'
                html += '</table></td></tr>'

            html += '<tr><td class=tinv colspan=4>&nbsp;</td></tr>'
            html += '</table>'

        html += '<br>'
        html += self._footer_html(chan_clean)
        return html

    # ── Page 4: Curiosities ────────────────────────────────────────────

    def _page4(self, channel, chan_clean, d):
        e = escape
        ranking = sorted(d["users"].items(), key=lambda x: x[1]["lines"], reverse=True)

        html = self._header_html(channel, chan_clean, f"{chan_clean}_p4.html", d)
        html += '<br><br>'
        html += self._legend()

        # ── Custom stats: Short words ──
        html += '<a name="cust"></a>'
        html += self._sh(f"Estos {len([1 for n,u in ranking if u['lines']>=5])} no saben que existen palabras con m\u00e1s de 4 letras.")
        short_users = []
        for nick, u in ranking:
            if u["lines"] >= 5:
                short_count = sum(1 for w in u["unique_words"] if len(w) <= 4)
                if short_count > 0:
                    short_users.append((nick, short_count))
        short_users.sort(key=lambda x: x[1], reverse=True)
        if short_users:
            html += '<table cellspacing=1 cellpadding=2 class=t2>'
            html += '<tr class=t1><td class=tinv>&nbsp;</td>'
            html += '<td class=ca> Nick </td>'
            html += '<td class=cb> N\u00famero de l\u00edneas </td>'
            html += '<td colspan=2 class=cc> L\u00ednea aleatoria </td></tr>'
            for i, (nick, count) in enumerate(short_users[:15]):
                u = d["users"][nick]
                bg_r = "cns" if i % 2 == 0 else "cn"
                bg_n = "cds" if i % 2 == 0 else "cd"
                bg_l = "ces" if i % 2 == 0 else "ce"
                bg_d = "cfs" if i % 2 == 0 else "cf"
                bg_q = "cfs" if i % 2 == 0 else "cf"
                bar_w = max(1, int(count / max(1, short_users[0][1]) * 80))
                q_text = ""
                q_date = ""
                if u["rand_quotes"]:
                    fq = u["rand_quotes"][0]
                    q_text = e(fq[3][:60])
                    if len(fq[3]) > 60:
                        q_text += "..."
                    q_date = f'{fq[0].strftime("%-d.%-m.")} {fq[1]:02d}:{fq[2]:02d}'
                html += f'<tr><td class="{bg_r} tar">{i+1}</td>'
                html += f'<td class="{bg_n}"><b>{e(nick)}</b></td>'
                html += f'<td class="{bg_l}">{self._pipe("pipecs.png", bar_w, 15)} {count}</td>'
                html += f'<td class="{bg_d} t6">{q_date}</td>'
                html += f'<td class="{bg_q} t5">"{q_text}"</td></tr>'
            html += '</table><br>'

        # ── URL spammers ──
        if d["urls_all"]:
            url_count = defaultdict(int)
            for _, _, _, nick, _ in d["urls_all"]:
                url_count[nick] += 1
            sorted_urls = sorted(url_count.items(), key=lambda x: x[1], reverse=True)[:10]
            if sorted_urls:
                html += self._sh("Top Spammers de Webs")
                html += '<table cellspacing=1 cellpadding=2 class=t2>'
                html += '<tr class=t1><td class=tinv>&nbsp;</td>'
                html += '<td class=ca> Nick </td>'
                html += '<td class=cb> N\u00famero de l\u00edneas </td>'
                html += '<td colspan=2 class=cc> L\u00ednea aleatoria </td></tr>'
                for i, (nick, count) in enumerate(sorted_urls):
                    u = d["users"].get(nick, {})
                    bg_r = "cns" if i % 2 == 0 else "cn"
                    bg_n = "cds" if i % 2 == 0 else "cd"
                    bg_l = "ces" if i % 2 == 0 else "ce"
                    bar_w = max(1, int(count / max(1, sorted_urls[0][1]) * 80))
                    q_text = ""
                    q_date = ""
                    if u and u.get("rand_quotes"):
                        fq = u["rand_quotes"][0]
                        q_text = e(fq[3][:60])
                        if len(fq[3]) > 60:
                            q_text += "..."
                        q_date = f'{fq[0].strftime("%-d.%-m.")} {fq[1]:02d}:{fq[2]:02d}'
                    html += f'<tr><td class="{bg_r} tar">{i+1}</td>'
                    html += f'<td class="{bg_n}"><b>{e(nick)}</b></td>'
                    html += f'<td class="{bg_l}">{self._pipe("pipecs.png", bar_w, 15)} {count}</td>'
                    html += f'<td class="cfs t6">{q_date}</td>'
                    html += f'<td class="cfs t5">"{q_text}"</td></tr>'
                html += '</table><br>'

        # ── URL Registry ──
        if d["urls_all"]:
            html += '<a name="urltr"></a>'
            html += self._sh("Registro de URLs", f"\u00daltimas 20 URLs de {e(channel)}")
            html += '<table border=0 cellspacing=1 cellpadding=2 class=t2><tr class=t1>'
            html += '<td class=ca>Fecha</td>'
            html += '<td class=cb>URL</td>'
            html += '<td class=cc>Nick</td></tr>'
            last_urls = d["urls_all"][-20:]
            for i, (fecha, hora, minuto, nick, url) in enumerate(last_urls):
                bg_d = "cds" if i % 2 == 0 else "cd"
                bg_u = "ces" if i % 2 == 0 else "ce"
                bg_n = "cfs" if i % 2 == 0 else "cf"

                url_display = url[:80] + "..." if len(url) > 80 else url
                date_str = f'{fecha.strftime("%-d.%-m.")} {hora:02d}:{minuto:02d}'

                # Check if first mention
                first_info = d.get("url_first_by", {}).get(url, None)
                extra = ""
                if first_info and first_info[0] != nick:
                    fnick, fdate, fhora, fmin = first_info
                    extra = f'<br><span class=t6>&nbsp;Primera menci\u00f3n por {e(fnick)} en {fdate.strftime("%-d.%-m.")} {fhora:02d}:{fmin:02d}.</span>'

                html += f'<tr><td class="{bg_d} t6">{date_str}</td>'
                html += f'<td class="{bg_u} t5"><a href="{e(url)}" class=t5 target="_blank">{e(url_display)}</a>{extra}</td>'
                html += f'<td class="{bg_n}">{e(nick)}</td></tr>'
            html += '</table><br>'

            # Random 20 URLs
            html += '<br><h5>20 p\u00e1ginas web al azar</h5>'
            random_urls = random.sample(d["urls_all"], min(20, len(d["urls_all"])))
            random_urls.sort(key=lambda x: x[0])
            html += '<table border=0 cellspacing=1 cellpadding=2 class=t2><tr class=t1>'
            html += '<td class=cas>Fecha</td>'
            html += '<td class=cbs>URL</td>'
            html += '<td class=ccs>Primer uso por</td></tr>'
            for i, (fecha, hora, minuto, nick, url) in enumerate(random_urls):
                bg_d = "cd" if i % 2 == 0 else "cds"
                bg_u = "ce" if i % 2 == 0 else "ces"
                bg_n = "cf" if i % 2 == 0 else "cfs"
                url_display = url[:80] + "..." if len(url) > 80 else url
                date_str = f'{fecha.strftime("%-d.%-m.")} {hora:02d}:{minuto:02d}'
                html += f'<tr><td class="{bg_d} t6">{date_str}</td>'
                html += f'<td class="{bg_u} t5"><a href="{e(url)}" class=t5 target="_blank">{e(url_display)}</a></td>'
                html += f'<td class="{bg_n}">{e(nick)}</td></tr>'
            html += '</table><br>'

            url_count_total = len(set(u for _, _, _, _, u in d["urls_all"]))
            html += f'<br><span class=txt2>{url_count_total} \u00fanicas URLs registradas</span><br><br>'

        html += self._footer_html(chan_clean)
        return html
