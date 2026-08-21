"""MiliPy — a Mineflayer-inspired automation framework for Mini Militia.

MiliPy provides a programmable Python bot API for player state, movement,
aiming, weapons, combat actions, player tracking, events, chat, and settings,
communicating with a Kotlin Android bridge over a versioned local WebSocket
protocol.

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
from .state import Capabilities, GameState, Player, Position, Vector, Weapon

__version__ = "0.1.0"
__all__ = [
    "Bot",
    "Capabilities",
    "CapabilityError",
    "EventEmitter",
    "GameState",
    "Player",
    "Position",
    "ProtocolError",
    "PROTOCOL_VERSION",
    "Vector",
    "Weapon",
]
