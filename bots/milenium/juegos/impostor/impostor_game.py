#!/usr/bin/env python3
"""
impostor_game.py — Lógica pura del juego Impostor (estilo Among Us).
Sin dependencias externas. Importa e integra con tu bot como quieras.

Cada método público devuelve una tupla:
    (ok: bool, public: str, private: dict[nick, str])

- ok:      True si la acción fue válida.
- public:  Mensaje para enviar al canal.
- private: Mensajes privados {nick: mensaje}. Dict vacío si no hay nada.
"""

import random
from enum import Enum, auto
from collections import defaultdict
from typing import Optional


# ══════════════════════════════════════════════
#  CONFIGURACION
# ══════════════════════════════════════════════
DEFAULT_CONFIG = {
    "min_players":      3,
    "impostor_ratio":   4,   # 1 impostor por cada N jugadores
    "tasks_per_player": 3,
}

TASKS = [
    "Repara el motor",
    "Recoge los suministros",
    "Sella la puerta",
    "Descifra el codigo",
    "Calibra los sensores",
    "Limpia los filtros de aire",
    "Recarga las baterias",
    "Actualiza los mapas de navegacion",
    "Inspecciona el casco",
    "Sincroniza los relojes",
]


# ══════════════════════════════════════════════
#  ENUMS
# ══════════════════════════════════════════════
class Role(Enum):
    CREWMATE = "Crewmate"
    IMPOSTOR = "Impostor"


class GameState(Enum):
    WAITING  = auto()
    IN_GAME  = auto()
    VOTING   = auto()
    FINISHED = auto()


# ══════════════════════════════════════════════
#  JUGADOR
# ══════════════════════════════════════════════
class Player:
    def __init__(self, nick: str):
        self.nick           = nick
        self.role: Optional[Role] = None
        self.alive          = True
        self.tasks_pending: list = []
        self.tasks_done:    list = []
        self.voted_for: Optional[str] = None
        self.kill_used      = False

    def assign_tasks(self, pool: list, n: int):
        self.tasks_pending = random.sample(pool, min(n, len(pool)))
        self.tasks_done    = []

    def complete_task(self, index: int) -> Optional[str]:
        """index es 1-based. Devuelve el nombre de la tarea o None si invalido."""
        i = index - 1
        if i < 0 or i >= len(self.tasks_pending):
            return None
        task = self.tasks_pending.pop(i)
        self.tasks_done.append(task)
        return task

    def reset_round(self):
        self.voted_for = None
        self.kill_used = False


# ══════════════════════════════════════════════
#  MOTOR DEL JUEGO
# ══════════════════════════════════════════════
class ImpostorGame:
    def __init__(self, config: dict = None):
        self.cfg = {**DEFAULT_CONFIG, **(config or {})}
        self.state:     GameState         = GameState.WAITING
        self.players:   dict              = {}   # nick -> Player
        self.impostors: set               = set()

    # ─ helpers ───────────────────────────────
    @property
    def alive_players(self) -> list:
        return [p for p in self.players.values() if p.alive]

    @property
    def alive_crew(self) -> list:
        return [p for p in self.alive_players if p.role == Role.CREWMATE]

    @property
    def alive_imp(self) -> list:
        return [p for p in self.alive_players if p.role == Role.IMPOSTOR]

    def _ok(self, public, private=None):
        return True, public, private or {}

    def _err(self, msg):
        return False, msg, {}

    def _check_victory(self):
        if not self.alive_imp:
            self.state = GameState.FINISHED
            return "crewmates", "Todos los impostores han sido eliminados. Los CREWMATES GANAN!"
        if len(self.alive_imp) >= len(self.alive_crew):
            self.state = GameState.FINISHED
            return "impostors", "Los impostores son mayoria. Los IMPOSTORES GANAN!"
        return None, None

    # ─ API publica ────────────────────────────

    def join(self, nick: str):
        if self.state != GameState.WAITING:
            return self._err("La partida ya esta en marcha.")
        if nick in self.players:
            return self._err(f"{nick} ya esta apuntado.")
        self.players[nick] = Player(nick)
        return self._ok(f"{nick} se ha unido. Jugadores: {len(self.players)}.")

    def leave(self, nick: str):
        if nick not in self.players:
            return self._err(f"{nick} no esta en la partida.")
        del self.players[nick]
        self.impostors.discard(nick)
        return self._ok(f"{nick} ha abandonado.")

    def start(self):
        min_p = self.cfg["min_players"]
        if self.state != GameState.WAITING:
            return self._err("La partida ya esta en marcha.")
        if len(self.players) < min_p:
            return self._err(f"Se necesitan al menos {min_p} jugadores (hay {len(self.players)}).")

        self.state = GameState.IN_GAME
        self.impostors.clear()

        nicks = list(self.players.keys())
        random.shuffle(nicks)
        n_imp = max(1, len(nicks) // self.cfg["impostor_ratio"])
        for nick in nicks[:n_imp]:
            self.players[nick].role = Role.IMPOSTOR
            self.impostors.add(nick)
        for nick in nicks[n_imp:]:
            self.players[nick].role = Role.CREWMATE

        n_tasks = self.cfg["tasks_per_player"]
        for p in self.players.values():
            p.alive = True
            p.reset_round()
            if p.role == Role.CREWMATE:
                p.assign_tasks(TASKS, n_tasks)

        private = {}
        for nick, p in self.players.items():
            if p.role == Role.IMPOSTOR:
                comps = [n for n in self.impostors if n != nick]
                comp_str = f" Complices: {', '.join(comps)}." if comps else ""
                private[nick] = f"Eres IMPOSTOR.{comp_str} Usa !kill <nick> para eliminar tripulantes."
            else:
                task_list = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(p.tasks_pending))
                private[nick] = f"Eres CREWMATE. Tus tareas:\n{task_list}"

        return self._ok(
            f"Partida iniciada con {len(self.players)} jugadores. Cada uno recibira su rol en privado.",
            private
        )

    def kill(self, killer_nick: str, target_nick: str):
        if self.state != GameState.IN_GAME:
            return self._err("No hay una partida en curso.")
        killer = self.players.get(killer_nick)
        target = self.players.get(target_nick)
        if not killer or not killer.alive or killer.role != Role.IMPOSTOR:
            return self._err("No puedes hacer eso.")
        if not target or not target.alive:
            return self._err(f"{target_nick} no existe o ya esta muerto.")
        if target_nick in self.impostors:
            return self._err("No puedes matar a otro impostor.")
        if killer.kill_used:
            return self._err("Ya mataste esta ronda. Espera a la proxima votacion.")

        target.alive = False
        killer.kill_used = True

        winner, win_msg = self._check_victory()
        if winner:
            return self._ok(f"Se ha encontrado el cadaver de {target_nick}. " + win_msg)
        return self._ok(f"Se ha encontrado el cadaver de {target_nick}.")

    def complete_task(self, nick: str, index: int):
        if self.state != GameState.IN_GAME:
            return self._err("No hay una partida en curso.")
        p = self.players.get(nick)
        if not p:
            return self._err(f"{nick} no esta en la partida.")
        if p.role != Role.CREWMATE:
            return self._err("Solo los crewmates tienen tareas.")
        if not p.alive:
            return self._err("Estas muerto.")

        task = p.complete_task(index)
        if task is None:
            n = len(p.tasks_pending)
            return self._err(f"Indice invalido. Tienes {n} tarea(s) pendiente(s) (1-{n}).")

        if all(len(p.tasks_pending) == 0 for p in self.players.values() if p.role == Role.CREWMATE):
            self.state = GameState.FINISHED
            return self._ok(
                f"{nick} completo la ultima tarea. Todos los tripulantes han terminado. CREWMATES GANAN!",
                {nick: f"Tarea completada: {task}."}
            )

        return self._ok(
            f"{nick} ha completado una tarea.",
            {nick: f"Tarea completada: {task}. Te quedan {len(p.tasks_pending)}."}
        )

    def get_tasks(self, nick: str):
        p = self.players.get(nick)
        if not p:
            return self._err(f"{nick} no esta en la partida.")
        if p.role == Role.IMPOSTOR:
            msg = "Eres impostor. No tienes tareas."
        elif not p.tasks_pending:
            msg = "Ya completaste todas tus tareas!"
        else:
            lines = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(p.tasks_pending))
            msg = f"Tareas pendientes:\n{lines}"
        return self._ok("", {nick: msg})

    def open_voting(self):
        if self.state != GameState.IN_GAME:
            return self._err("Solo se puede votar durante la partida.")
        self.state = GameState.VOTING
        for p in self.players.values():
            p.reset_round()
        alive_list = ", ".join(p.nick for p in self.alive_players)
        return self._ok(f"Votacion abierta! Vivos: {alive_list}. Usa !vote <nick> o !vote skip.")

    def vote(self, voter_nick: str, target_nick: str):
        if self.state != GameState.VOTING:
            return self._err("No hay una votacion activa.")
        voter = self.players.get(voter_nick)
        if not voter or not voter.alive:
            return self._err("No puedes votar.")
        if voter.voted_for is not None:
            return self._err(f"Ya votaste por {voter.voted_for}.")
        skip = target_nick.lower() == "skip"
        if not skip:
            target = self.players.get(target_nick)
            if not target or not target.alive:
                return self._err(f"{target_nick} no es un jugador vivo.")
            if target_nick == voter_nick:
                return self._err("No puedes votarte a ti mismo.")
        voter.voted_for = target_nick
        pending = [p.nick for p in self.alive_players if p.voted_for is None]
        extra = f" Pendientes: {', '.join(pending)}." if pending else " Todos han votado!"
        return self._ok(f"{voter_nick} ha votado.{extra}")

    def tally(self):
        if self.state != GameState.VOTING:
            return self._err("No hay una votacion activa.")

        count = defaultdict(int)
        for p in self.alive_players:
            if p.voted_for and p.voted_for.lower() != "skip":
                count[p.voted_for] += 1

        summary = "\n".join(
            f"  {n}: {v} voto(s)" for n, v in sorted(count.items(), key=lambda x: -x[1])
        ) or "  (nadie recibio votos)"

        if not count:
            self.state = GameState.IN_GAME
            return self._ok(f"Resultado:\n{summary}\nNadie expulsado. La partida continua.")

        max_v      = max(count.values())
        candidates = [n for n, v in count.items() if v == max_v]

        if len(candidates) > 1:
            self.state = GameState.IN_GAME
            return self._ok(
                f"Resultado:\n{summary}\n"
                f"Empate entre {', '.join(candidates)}. Nadie expulsado. La partida continua."
            )

        expelled = candidates[0]
        self.players[expelled].alive = False
        role_str = self.players[expelled].role.value
        msg = f"Resultado:\n{summary}\n{expelled} expulsado. Era un {role_str}."

        winner, win_msg = self._check_victory()
        if winner:
            return self._ok(msg + "\n" + win_msg)

        self.state = GameState.IN_GAME
        return self._ok(msg + "\nLa partida continua.")

    def status(self) -> str:
        if self.state == GameState.WAITING:
            nicks = ", ".join(self.players) or "(ninguno)"
            return f"Estado: ESPERANDO | Jugadores: {nicks}"
        if self.state == GameState.FINISHED:
            return "La partida ha terminado. Usa !join para la siguiente."
        alive = ", ".join(p.nick for p in self.alive_players)
        dead  = ", ".join(p.nick for p in self.players.values() if not p.alive)
        phase = "EN PARTIDA" if self.state == GameState.IN_GAME else "VOTACION"
        s = f"Estado: {phase} | Vivos: {alive}"
        if dead:
            s += f" | Muertos: {dead}"
        return s

    def reset(self):
        self.__init__(self.cfg)
        return self._ok("Partida reiniciada.")
