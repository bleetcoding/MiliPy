"""MiliPy — a Mineflayer-inspired automation framework for Mini Militia.

MiliPy is a Mineflayer-style standalone client whose core target is the
**Mini Militia LAN multiplayer protocol** itself: the Python process runs
entirely from Termux and appears on the local network as an ordinary LAN
client/player of a Mini Militia LAN host (see
``protocol/lan-protocol-research.md``).

Protocol honesty model — every wire-format claim is tagged:

- **KNOWN** — established by multiple independent public sources
- **OBSERVED** — captured by MiliPy's own framework against a real host
- **INFERRED** — an untested hypothesis, never trusted by the codec
- **UNKNOWN** — no evidence; the capture/replay framework fills these gaps

Until LAN packet formats have been validated by capture round-trips, the
core codec is ``UNKNOWN`` and ``Bot("<host>")`` raises ``CapabilityError``
rather than fabricating support. The bot can still be driven offline by
``SimAdapter`` (a labeled stand-in) or by the optional **experimental
Android bridge** (``experimental/bridge/`` — screen automation kept from
earlier rounds).

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
from .state import CapabilityStatus, Capabilities, GameSession, GameState, Player, Position, Vector, Weapon

__version__ = "0.4.0"
__all__ = [
    "Bot",
    "Capabilities",
    "CapabilityError",
    "CapabilityStatus",
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
