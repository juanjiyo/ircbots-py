#!/usr/bin/env python3
"""
bingo_game.py — Lógica pura del juego de Bingo.
Sin dependencias externas. Importa e integra con tu bot como quieras.

Cada método público devuelve una tupla:
    (ok: bool, public: str, private: dict[nick, str])

- ok:      True si la acción fue válida.
- public:  Mensaje para enviar al canal.
- private: Mensajes privados {nick: mensaje}. Dict vacío si no aplica.
"""

import random
from typing import Optional


# ══════════════════════════════════════════════
#  CONFIGURACIÓN
# ══════════════════════════════════════════════
COLUMNS = {
    'B': (1,  15),
    'I': (16, 30),
    'N': (31, 45),
    'G': (46, 60),
    'O': (61, 75),
}
FREE_CELL = (2, 2)   # fila 2, columna 2 (0-based) → centro de la carta


# ══════════════════════════════════════════════
#  CARTA DE BINGO
# ══════════════════════════════════════════════
class BingoCard:
    def __init__(self, nick: str):
        self.nick = nick
        self.grid: list[list[Optional[int]]] = self._generate()
        self.marked: set[int] = set()   # números marcados (None = FREE siempre marcado)

    def _generate(self) -> list[list[Optional[int]]]:
        cols = {}
        for letter, (lo, hi) in COLUMNS.items():
            pool = list(range(lo, hi + 1))
            if letter == 'N':
                sample = random.sample(pool, 4)
                sample.insert(FREE_CELL[0], None)   # casilla libre en el centro
            else:
                sample = random.sample(pool, 5)
            cols[letter] = sample

        return [
            [cols[col][row] for col in 'BINGO']
            for row in range(5)
        ]

    def mark(self, number: int) -> bool:
        """Marca el número en la carta si existe. Devuelve True si estaba."""
        for row in self.grid:
            if number in row:
                self.marked.add(number)
                return True
        return False

    def has_bingo(self) -> bool:
        """Comprueba si la carta tiene bingo (fila, columna o diagonal)."""
        def cell_marked(r, c) -> bool:
            val = self.grid[r][c]
            return val is None or val in self.marked

        # Filas
        for r in range(5):
            if all(cell_marked(r, c) for c in range(5)):
                return True
        # Columnas
        for c in range(5):
            if all(cell_marked(r, c) for r in range(5)):
                return True
        # Diagonales
        if all(cell_marked(i, i) for i in range(5)):
            return True
        if all(cell_marked(i, 4 - i) for i in range(5)):
            return True
        return False

    def format(self) -> str:
        """Devuelve la carta formateada como texto para enviar por privado."""
        header = "  B    I    N    G    O"
        lines = [header, "-" * len(header)]
        for row in self.grid:
            parts = []
            for cell in row:
                if cell is None:
                    parts.append(" FREE")
                else:
                    parts.append(f"{cell:>4} ")
            lines.append(" ".join(parts))
        return "\n".join(lines)

    def letter_of(self, number: int) -> Optional[str]:
        for letter, (lo, hi) in COLUMNS.items():
            if lo <= number <= hi:
                return letter
        return None


# ══════════════════════════════════════════════
#  MOTOR DEL JUEGO
# ══════════════════════════════════════════════
class BingoGame:
    def __init__(self):
        self.players:  dict[str, BingoCard] = {}
        self.bag:      list[int]            = []   # números pendientes de sacar
        self.drawn:    list[int]            = []   # números ya sacados
        self.running:  bool                 = False
        self.finished: bool                 = False

    # ─ helpers ───────────────────────────────
    def _ok(self, public, private=None):
        return True, public, private or {}

    def _err(self, msg):
        return False, msg, {}

    # ─ API pública ────────────────────────────

    def join(self, nick: str):
        """Un jugador pide una carta."""
        if self.running:
            return self._err("La partida ya está en marcha.")
        if nick in self.players:
            return self._err(f"{nick} ya tiene una carta.")
        card = BingoCard(nick)
        self.players[nick] = card
        return self._ok(
            f" {nick} se ha apuntado al bingo. Jugadores: {len(self.players)}.",
            {nick: f"Tu carta de bingo:\n{card.format()}"}
        )

    def leave(self, nick: str):
        if nick not in self.players:
            return self._err(f"{nick} no está en la partida.")
        del self.players[nick]
        return self._ok(f" {nick} ha abandonado.")

    def start(self):
        """Inicia la partida y envía las cartas en privado."""
        if self.running:
            return self._err("La partida ya está en marcha.")
        if not self.players:
            return self._err("No hay jugadores apuntados.")

        self.running  = True
        self.finished = False
        self.bag      = list(range(1, 76))
        random.shuffle(self.bag)
        self.drawn    = []

        private = {
            nick: f"¡Empieza el bingo! Tu carta:\n{card.format()}"
            for nick, card in self.players.items()
        }
        return self._ok(
            f" ¡Bingo iniciado con {len(self.players)} jugador(es)! "
            f"Cada uno ha recibido su carta en privado. Usa !draw para sacar números.",
            private
        )

    def draw(self):
        """Saca el siguiente número de la bolsa."""
        if not self.running:
            return self._err("La partida no ha comenzado. Usa !start.")
        if self.finished:
            return self._err("La partida ya ha terminado.")
        if not self.bag:
            return self._err("Se han sacado todos los números (1-75) sin ganador.")

        number = self.bag.pop()
        self.drawn.append(number)
        letter = next(l for l, (lo, hi) in COLUMNS.items() if lo <= number <= hi)

        # Marcar en todas las cartas
        for card in self.players.values():
            card.mark(number)

        drawn_count = len(self.drawn)
        return self._ok(
            f" {letter}-{number}  ({drawn_count}/75 sacados)"
        )

    def check_bingo(self, nick: str):
        """Un jugador canta bingo. Se verifica su carta."""
        if not self.running:
            return self._err("No hay una partida en curso.")
        if self.finished:
            return self._err("La partida ya ha terminado.")
        card = self.players.get(nick)
        if not card:
            return self._err(f"{nick} no está en la partida.")

        if card.has_bingo():
            self.finished = True
            self.running  = False
            return self._ok(
                f" ¡BINGO! {nick} ha ganado con los números: {sorted(card.marked)}. "
                f"Se han sacado {len(self.drawn)} números en total."
            )
        else:
            return self._ok(
                f" {nick} ha cantado bingo pero su carta no es válida. ¡La partida continúa!"
            )

    def get_card(self, nick: str):
        """Reenvía la carta de un jugador en privado."""
        card = self.players.get(nick)
        if not card:
            return self._err(f"{nick} no tiene carta en esta partida.")
        state = f"Números sacados hasta ahora: {self.drawn if self.drawn else '(ninguno)'}"
        return self._ok("", {nick: f"Tu carta:\n{card.format()}\n{state}"})

    def drawn_numbers(self) -> str:
        """Devuelve un string con los números sacados, agrupados por letra."""
        if not self.drawn:
            return "No se ha sacado ningún número todavía."
        groups = {l: [] for l in 'BINGO'}
        for n in self.drawn:
            for letter, (lo, hi) in COLUMNS.items():
                if lo <= n <= hi:
                    groups[letter].append(n)
        lines = [f"  {l}: {sorted(v)}" for l, v in groups.items() if v]
        return "Números sacados:\n" + "\n".join(lines)

    def status(self) -> str:
        if not self.running and not self.finished:
            nicks = ", ".join(self.players) or "(ninguno)"
            return f"Estado: ESPERANDO | Jugadores: {nicks}"
        if self.finished:
            return "La partida ha terminado. Usa !join para la siguiente."
        return (
            f"Estado: EN CURSO | Jugadores: {len(self.players)} | "
            f"Números sacados: {len(self.drawn)}/75"
        )

    def reset(self):
        """Reinicia completamente la partida."""
        self.__init__()
        return self._ok(" Partida de bingo reiniciada.")
