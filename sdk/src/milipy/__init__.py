"""MiliPy — a Mineflayer-inspired automation framework for Mini Militia.

MiliPy is a programmable control/observation framework for a *normal* Mini
Militia Android client, working through a local Kotlin Android bridge.

Two separate networking layers exist and must not be confused:

- **Mini Militia LAN networking** — handled entirely by the game itself
  (hotspot, LAN lobby, matchmaking). MiliPy neither implements nor replaces it.
- **MiliPy control networking** — the Python SDK talks only to the MiliPy
  Android Bridge over a versioned local WebSocket. The ``Bot``'s ``host``
  parameter is the bridge's address, never the game's.

The SDK exposes player state, movement, aiming, weapons, combat actions,
player tracking, events, chat, and settings on top of that bridge connection.

Example::

    from milipy import Bot

    bot = Bot("192.168.43.1")

    @bot.on("ready")
    def ready():
        print("MiliPy bot ready")

    bot.connect()
    bot.run()

The public surface intentionally stays small: :class:`Bot` for the main API,
state models in :mod:`milipy.state`, the protocol schema in
:mod:`milipy.protocol_schema`, and the simulator in :mod:`milipy.sim`.
"""

from .bot import Bot
from .events import EventEmitter
from .protocol import CapabilityError, ProtocolError
from .protocol_schema import PROTOCOL_VERSION
from .sim import SimAdapter, SimWorld
from .state import Capabilities, GameSession, GameState, Player, Position, Vector, Weapon

__version__ = "0.1.0"
__all__ = [
    "Bot",
    "Capabilities",
    "CapabilityError",
    "EventEmitter",
    "GameSession",
    "GameState",
    "Player",
    "Position",
    "ProtocolError",
    "PROTOCOL_VERSION",
    "SimAdapter",
    "SimWorld",
    "Vector",
    "Weapon",
]
