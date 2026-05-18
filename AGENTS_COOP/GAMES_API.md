# Documentación de módulos de juego para bot IRC

Módulos Python de lógica pura para integrar en un bot IRC (o cualquier otro cliente).
**Sin dependencias externas.** Ninguno de los dos módulos sabe nada de IRC, sockets ni red.

---

## Convención de retorno común

Todos los métodos públicos de ambos módulos devuelven **la misma tupla de tres elementos**:

```python
(ok: bool, public: str, private: dict[str, str])
```

| Campo | Tipo | Descripción |
|---|---|---|
| `ok` | `bool` | `True` si la acción fue válida y se ejecutó. `False` si hubo un error. |
| `public` | `str` | Mensaje para enviar al canal. Puede ser `""` si no hay nada que decir en público. |
| `private` | `dict` | Mensajes privados `{nick: mensaje}`. Dict vacío si no hay nada que mandar en privado. |

### Patrón de integración en el bot

```python
ok, public, private = game.algún_método(...)

if public:
    bot.say(canal, public)

for nick, msg in private.items():
    bot.privmsg(nick, msg)   # o notice(), según tu bot
```

> Si `ok` es `False`, `public` contiene el mensaje de error listo para enviar al canal o al usuario.

---

## Flujo de estados

### `ImpostorGame`

```
WAITING → (start) → IN_GAME ⇄ (open_voting) → VOTING
                                    ↓ (tally, victoria)
                                 FINISHED
```

### `BingoGame`

```
(sin partida) → (start) → EN CURSO → (check_bingo / bolsa vacía) → FINISHED
```

---

## Módulo `impostor_game.py`

Juego estilo *Among Us*. Los jugadores reciben roles secretos (Crewmate o Impostor).
Los crewmates ganan completando sus tareas o expulsando a todos los impostores en votación.
Los impostores ganan si igualan o superan en número a los crewmates vivos.

### Configuración

```python
from impostor_game import ImpostorGame

# Valores por defecto
DEFAULT_CONFIG = {
    "min_players":      3,   # mínimo de jugadores para iniciar
    "impostor_ratio":   4,   # 1 impostor por cada N jugadores
    "tasks_per_player": 3,   # tareas asignadas a cada crewmate
}

# Instanciar con config personalizada (todos los campos son opcionales)
game = ImpostorGame(config={"min_players": 2, "tasks_per_player": 2})
```

### Enums

#### `Role`
| Valor | Descripción |
|---|---|
| `Role.CREWMATE` | Tripulante. Debe completar tareas y votar al impostor. |
| `Role.IMPOSTOR` | Impostor. Debe eliminar tripulantes sin ser descubierto. |

#### `GameState`
| Valor | Descripción |
|---|---|
| `GameState.WAITING` | Esperando jugadores. Se pueden unir con `join()`. |
| `GameState.IN_GAME` | Partida en curso. Se pueden completar tareas y matar. |
| `GameState.VOTING` | Fase de votación abierta. |
| `GameState.FINISHED` | Partida terminada. Hay que llamar a `reset()` para otra. |

### Clase `Player` (interna)

No se instancia directamente. Se accede a través de `game.players[nick]`.

| Atributo | Tipo | Descripción |
|---|---|---|
| `nick` | `str` | Nombre del jugador. |
| `role` | `Role` | Rol asignado. `None` antes de `start()`. |
| `alive` | `bool` | `True` si el jugador sigue vivo. |
| `tasks_pending` | `list[str]` | Tareas que aún le quedan por completar. |
| `tasks_done` | `list[str]` | Tareas ya completadas. |
| `voted_for` | `str \| None` | Nick votado en la ronda actual. `None` si aún no ha votado. |
| `kill_used` | `bool` | `True` si el impostor ya mató en esta ronda. |

### API pública de `ImpostorGame`

---

#### `join(nick: str)`

Un jugador se une a la partida. Solo funciona en estado `WAITING`.

```python
ok, public, private = game.join("Alice")
# public → "Alice se ha unido. Jugadores: 1."
# private → {}
```

**Errores posibles:** partida ya en marcha, nick duplicado.

---

#### `leave(nick: str)`

Un jugador abandona la partida.

```python
ok, public, private = game.leave("Alice")
# public → "Alice ha abandonado."
```

**Errores posibles:** nick no encontrado.

---

#### `start()`

Inicia la partida. Asigna roles y tareas aleatoriamente. Envía el rol a cada jugador en privado.

```python
ok, public, private = game.start()
# public  → "Partida iniciada con 4 jugadores. Cada uno recibirá su rol en privado."
# private → {
#   "Alice": "Eres CREWMATE. Tus tareas:\n  1. Repara el motor\n  2. ...",
#   "Bob":   "Eres IMPOSTOR. Usa !kill <nick> para eliminar tripulantes.",
#   ...
# }
```

**Errores posibles:** partida ya en marcha, jugadores insuficientes.

---

#### `kill(killer_nick: str, target_nick: str)`

Un impostor elimina a un tripulante. Recomendado recibirlo por PRIVMSG al bot.
Cada impostor solo puede matar **una vez por ronda** (se resetea al abrir votación).

```python
ok, public, private = game.kill("Bob", "Carol")
# public → "Se ha encontrado el cadáver de Carol."
# Si es la última muerte necesaria para ganar:
# public → "Se ha encontrado el cadáver de Carol. Los impostores son mayoría. Los IMPOSTORES GANAN!"
```

**Errores posibles:** no hay partida, el killer no es impostor o está muerto, target ya muerto, target es otro impostor, kill ya usado esta ronda.

---

#### `complete_task(nick: str, index: int)`

Un crewmate completa la tarea número `index` (índice **1-based**).

```python
ok, public, private = game.complete_task("Alice", 1)
# public  → "Alice ha completado una tarea."
# private → {"Alice": "Tarea completada: Repara el motor. Te quedan 2."}

# Si era la última tarea de todos los crewmates:
# public → "Alice completó la última tarea. Todos los tripulantes han terminado. CREWMATES GANAN!"
```

**Errores posibles:** no hay partida, nick no existe, el jugador es impostor o está muerto, índice fuera de rango.

---

#### `get_tasks(nick: str)`

Reenvía la lista de tareas pendientes al jugador en privado. No dice nada en el canal.

```python
ok, public, private = game.get_tasks("Alice")
# public  → ""
# private → {"Alice": "Tareas pendientes:\n  1. Repara el motor\n  2. Sella la puerta"}
```

---

#### `open_voting()`

Abre la fase de votación. Solo funciona en estado `IN_GAME`.
Resetea los flags de `kill_used` y `voted_for` de todos los jugadores.

```python
ok, public, private = game.open_voting()
# public → "Votacion abierta! Vivos: Alice, Bob, Carol. Usa !vote <nick> o !vote skip."
```

**Errores posibles:** no hay partida en curso.

---

#### `vote(voter_nick: str, target_nick: str)`

Registra el voto de un jugador. `target_nick` puede ser `"skip"` para abstenerse.
Solo funciona en estado `VOTING`.

```python
ok, public, private = game.vote("Alice", "Bob")
# public → "Alice ha votado. Pendientes: Carol."

ok, public, private = game.vote("Carol", "skip")
# public → "Carol ha votado. Todos han votado!"
```

**Errores posibles:** no hay votación activa, el votante no está vivo, voto ya emitido, target inválido, auto-voto.

---

#### `tally()`

Cierra la votación, cuenta los votos y expulsa al jugador más votado.
En caso de empate, nadie es expulsado. Comprueba victoria tras la expulsión.

```python
ok, public, private = game.tally()
# public → "Resultado:\n  Bob: 2 voto(s)\n  Alice: 1 voto(s)\nBob expulsado. Era un Impostor.\nLa partida continua."

# Con victoria:
# public → "...Bob expulsado. Era un Impostor.\nTodos los impostores han sido eliminados. Los CREWMATES GANAN!"
```

**Errores posibles:** no hay votación activa.

---

#### `status() → str`

Devuelve un string (no una tupla) con el estado actual de la partida.

```python
print(game.status())
# "Estado: EN PARTIDA | Vivos: Alice, Carol | Muertos: Bob"
# "Estado: ESPERANDO | Jugadores: Alice, Bob"
# "La partida ha terminado. Usa !join para la siguiente."
```

---

#### `reset()`

Reinicia completamente la partida. Borra jugadores, roles y estado.

```python
ok, public, private = game.reset()
# public → "Partida reiniciada."
```

---

### Condiciones de victoria

| Ganador | Condición |
|---|---|
| **Crewmates** | Todos los impostores han sido expulsados o muertos. |
| **Crewmates** | Todos los crewmates han completado sus tareas. |
| **Impostores** | El número de impostores vivos ≥ número de crewmates vivos. |

La victoria se comprueba automáticamente después de cada `kill()`, `complete_task()` y `tally()`.

---

### Ejemplo de flujo completo

```python
game = ImpostorGame()

game.join("Alice")
game.join("Bob")
game.join("Carol")
game.join("Dave")

ok, pub, priv = game.start()
# → enviar pub al canal, enviar priv[nick] a cada nick en privado

# Carol es impostor → desde su PRIVMSG al bot:
game.kill("Carol", "Dave")

# Alice abre votación:
game.open_voting()
game.vote("Alice", "Carol")
game.vote("Bob", "Carol")
game.vote("Carol", "skip")
game.tally()   # expulsa a Carol → CREWMATES GANAN
```

---

---

## Módulo `bingo_game.py`

Bingo estándar de 5×5 con casilla FREE central. Bolsa de 75 números (B1-O75).
Gana el primero en completar una línea (fila, columna o diagonal) y cantarlo con `check_bingo()`.

### Distribución de columnas

| Columna | Rango |
|---|---|
| B | 1 – 15 |
| I | 16 – 30 |
| N | 31 – 45 |
| G | 46 – 60 |
| O | 61 – 75 |

La casilla central (fila 2, columna N, índice `[2][2]`) es siempre `FREE` y cuenta como marcada.

### Clase `BingoCard` (interna)

No se instancia directamente. Se crea al llamar a `join()` y se accede a través de `game.players[nick]`.

| Atributo | Tipo | Descripción |
|---|---|---|
| `nick` | `str` | Nick del propietario. |
| `grid` | `list[list[int\|None]]` | Cuadrícula 5×5. `None` = casilla FREE. |
| `marked` | `set[int]` | Números marcados hasta el momento. |

| Método | Descripción |
|---|---|
| `mark(number)` | Marca el número si está en la carta. Llamado automáticamente por `draw()`. |
| `has_bingo()` | Comprueba filas, columnas y las dos diagonales. |
| `format()` | Devuelve la carta como texto formateado para enviar por privado. |

### API pública de `BingoGame`

---

#### `join(nick: str)`

Un jugador solicita una carta. La carta se genera y se envía en privado. Solo antes de `start()`.

```python
ok, public, private = game.join("Alice")
# public  → "✅ Alice se ha apuntado al bingo. Jugadores: 1."
# private → {"Alice": "Tu carta de bingo:\n  B    I    N    G    O\n---..."}
```

**Errores posibles:** partida ya en marcha, nick duplicado.

---

#### `leave(nick: str)`

Un jugador abandona.

```python
ok, public, private = game.leave("Alice")
# public → "🚪 Alice ha abandonado."
```

---

#### `start()`

Inicia la partida. Baraja la bolsa de 75 números y reenvía las cartas a todos en privado.

```python
ok, public, private = game.start()
# public  → "🎱 ¡Bingo iniciado con 3 jugador(es)! Cada uno ha recibido su carta en privado. Usa !draw para sacar números."
# private → {"Alice": "¡Empieza el bingo! Tu carta:\n...", "Bob": "...", ...}
```

**Errores posibles:** partida ya en marcha, sin jugadores.

---

#### `draw()`

Saca el siguiente número de la bolsa y lo marca automáticamente en todas las cartas.

```python
ok, public, private = game.draw()
# public → "🎱 B-7  (1/75 sacados)"
# public → "🎱 N-38  (12/75 sacados)"
```

**Errores posibles:** partida no iniciada, ya terminada, bolsa vacía (75 números agotados sin ganador).

---

#### `check_bingo(nick: str)`

Un jugador canta bingo. El motor verifica su carta.
Si es válido, la partida termina. Si no, continúa sin penalización.

```python
ok, public, private = game.check_bingo("Alice")
# Válido:
# public → "🏆 ¡BINGO! Alice ha ganado con los números: [3, 17, 38, 52, 65]. Se han sacado 23 números en total."

# Inválido:
# public → "❌ Alice ha cantado bingo pero su carta no es válida. ¡La partida continúa!"
```

**Errores posibles:** partida no iniciada, ya terminada, nick no encontrado.

---

#### `get_card(nick: str)`

Reenvía la carta actualizada al jugador en privado. No dice nada en el canal.

```python
ok, public, private = game.get_card("Alice")
# public  → ""
# private → {"Alice": "Tu carta:\n  B    I ...\nNúmeros sacados hasta ahora: [7, 23, ...]"}
```

---

#### `drawn_numbers() → str`

Devuelve un string (no una tupla) con todos los números sacados, agrupados por columna.

```python
print(game.drawn_numbers())
# "Números sacados:
#    B: [3, 11]
#    I: [23]
#    N: [38, 42]
#    O: [65]"
```

---

#### `status() → str`

Devuelve un string (no una tupla) con el estado actual.

```python
print(game.status())
# "Estado: ESPERANDO | Jugadores: Alice, Bob"
# "Estado: EN CURSO | Jugadores: 3 | Números sacados: 12/75"
# "La partida ha terminado. Usa !join para la siguiente."
```

---

#### `reset()`

Reinicia completamente la partida. Borra jugadores, cartas y bolsa.

```python
ok, public, private = game.reset()
# public → "🔄 Partida de bingo reiniciada."
```

---

### Ejemplo de flujo completo

```python
game = BingoGame()

game.join("Alice")   # le llega su carta en privado
game.join("Bob")
game.join("Carol")

game.start()         # se reenvían las cartas y se baraja la bolsa

# El bot saca un número cada X segundos o cuando alguien usa el comando:
for _ in range(30):
    ok, pub, _ = game.draw()
    bot.say(canal, pub)

    # Si alguien grita "!bingo" en el canal:
    ok, pub, _ = game.check_bingo("Alice")
    bot.say(canal, pub)
    if ok and "BINGO" in pub:
        break   # partida terminada
```

---

## Referencia rápida de métodos

### `ImpostorGame`

| Método | Estado requerido | Devuelve tupla | Descripción |
|---|---|---|---|
| `join(nick)` | `WAITING` | ✅ | Añade un jugador. |
| `leave(nick)` | cualquiera | ✅ | Elimina un jugador. |
| `start()` | `WAITING` | ✅ | Inicia la partida y asigna roles. |
| `kill(killer, target)` | `IN_GAME` | ✅ | El impostor mata a un tripulante. |
| `complete_task(nick, n)` | `IN_GAME` | ✅ | El crewmate completa la tarea n. |
| `get_tasks(nick)` | cualquiera | ✅ | Envía tareas pendientes en privado. |
| `open_voting()` | `IN_GAME` | ✅ | Abre la fase de votación. |
| `vote(voter, target)` | `VOTING` | ✅ | Registra un voto (`"skip"` para abstenerse). |
| `tally()` | `VOTING` | ✅ | Cierra la votación y expulsa al más votado. |
| `status()` | cualquiera | ❌ (str) | Estado actual como texto. |
| `reset()` | cualquiera | ✅ | Reinicia todo. |

### `BingoGame`

| Método | Descripción | Devuelve tupla |
|---|---|---|
| `join(nick)` | Añade jugador y genera su carta. | ✅ |
| `leave(nick)` | Elimina jugador. | ✅ |
| `start()` | Inicia la partida. | ✅ |
| `draw()` | Saca el siguiente número. | ✅ |
| `check_bingo(nick)` | Verifica si el jugador tiene bingo. | ✅ |
| `get_card(nick)` | Reenvía la carta en privado. | ✅ |
| `drawn_numbers()` | Lista de números sacados por columna. | ❌ (str) |
| `status()` | Estado actual como texto. | ❌ (str) |
| `reset()` | Reinicia todo. | ✅ |
