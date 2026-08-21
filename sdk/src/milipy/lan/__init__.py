"""Mini Militia LAN client layer (scaffold).

This is the future home of the standalone protocol client: `LANAdapter`
speaks directly to a Mini Militia LAN host and `MiniMilitiaCodec` turns raw
UDP bytes into Bot events.

HONEST STATUS (Aug 2026): the Mini Militia LAN packet format is UNKNOWN.
No public documentation or implementation exists anywhere, and no capture
has been analyzed yet. This module exists as a prepared scaffold: connecting
to a real host raises `CapabilityError` with a pointer to
`protocol/lan-protocol-research.md` until interoperability is demonstrated
against a real LAN host. Do not claim LAN support before then.

What IS implemented and tested here:
- The adapter/event wiring against a test UDP server (see tests/test_lan_adapter.py)
- The codec parse skeleton: a future `_decode_packet` that MUST be filled in
  from real capture evidence, never invented.

The API shape mirrors Mineflayer: `Bot.connect()` → `bot.on("player_join")`
→ `bot.aim_at(p)` → `bot.fire()` → `bot.disconnect()`.
"""
from milipy.lan.adapter import LANAdapter
from milipy.lan.codec import MiniMilitiaCodec

__all__ = ["LANAdapter", "MiniMilitiaCodec"]
