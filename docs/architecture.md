# MiliPy Architecture

## What MiliPy is

MiliPy is a **Mineflayer-style standalone Mini Militia client**. The Python process
runs entirely from Termux and speaks the **Mini Militia LAN multiplayer protocol
directly**, appearing on the network as an ordinary LAN client/player — no phone,
no screen capture, no injected automation is required for the core bot.

```
Termux
  |
  | Python MiliPy
  | Mini Militia LAN protocol (UDP)
  v
Mini Militia LAN host
```

MiliPy is deliberately **not** an RL agent, not a fake network client that pretends
to work, and not a screen-automation wrapper. The design goal is the same one
Mineflayer achieves for Minecraft: a high-level, event-driven bot API built on a
faithful implementation of the game's real network protocol, with a
server-authoritative world model that only reflects what the host actually sends.

## Two components, clearly separated

| Component | Path | Status |
|---|---|---|
| **Core LAN client** (the bot) | `sdk/src/milipy/` | **Primary.** Mineflayer-like Bot + the protocol research layer |
| **Android bridge** (screen automation) | `experimental/bridge/` | **Optional, experimental.** Kept from earlier rounds; not required by the core bot |

The core bot talks to Mini Militia hosts. The Android bridge automates a real
Android screen via `MediaProjection` + Accessibility Service and remains available
for users who prefer observation-of-a-screen over protocol-level play. The two are
never mixed: a Bot instance targets the LAN protocol; the bridge has its own
WebSocket protocol (see `protocol/protocol.md`).

## The Mineflayer pattern MiliPy follows

Mineflayer ([PrismarineJS/mineflayer](https://github.com/PrismarineJS/mineflayer))
creates Minecraft bots that connect directly to a Minecraft server and speak the
real Minecraft protocol, indistinguishable from a normal client at the wire level.
Its architecture has four layers, and MiliPy mirrors them:

| Mineflayer layer | Role | MiliPy equivalent |
|---|---|---|
| `node-minecraft-protocol` | packet parsing/serialization, keep-alive, encryption | `milipy.lan` (packet codec — built from captures) |
| `minecraft-data` | per-version packet definitions | `milipy.lan.packets` (definitions — built from captures) |
| `prismarine-*` (entity, world, physics…) | domain objects fed by incoming packets | `milipy` state models (`Player`, `Weapon`, `GameState`) |
| `mineflayer` Bot | event-driven high-level API over the models | `milipy.Bot` (existing event core, retargeted) |

The bot API mirrors the requested Mineflayer shape:

```python
from milipy import Bot

bot = Bot("192.168.1.x")

bot.on("spawn", on_spawn)
bot.on("player_join", on_join)
bot.on("player_leave", on_leave)

bot.connect()
bot.join_lobby()

target = bot.nearest_enemy()
bot.aim_at(target)
bot.fire()

bot.disconnect()
```

## Protocol honesty model

Mini Militia has **no published LAN protocol documentation**, and no public
implementation was found anywhere (searched August 2026). Therefore MiliPy adopts a
four-level certainty model, enforced in code:

| Level | Meaning |
|---|---|
| **KNOWN** | Established by multiple independent public sources |
| **OBSERVED** | Captured by MiliPy's own framework against a real LAN host |
| **INFERRED** | A hypothesis that has NOT been tested — never trusted by the codec |
| **UNKNOWN** | No evidence — the research framework exists to fill these |

The research document is [`protocol/lan-protocol-research.md`](../protocol/lan-protocol-research.md).
The capture/replay framework (`protocol/research/capture.py`, `analyze.py`,
`replay.py`) turns UNKNOWN into OBSERVED: capture real traffic while performing
tagged in-game actions, run structure probes, and validate every decoding
hypothesis with a send/receive round-trip against the real game. **No packet
format is fabricated**, and Mini Militia protocol support is never claimed until a
capture round-trip against a real LAN host has succeeded.

## What is KNOWN so far (public sources)

Mini Militia — Doodle Army 2 LAN multiplayer runs over a local Wi-Fi network (a
phone hotspot with everyone joined), needs no internet, uses a **host–client
topology** where one player's phone hosts the game session, and uses **UDP** for
gameplay traffic. The host phone runs the session authoritatively, exactly like a
game server. The game's official online servers shut down in 2024, so LAN play is
the only surviving multiplayer mode. All packet-level details — discovery,
handshake, join, spawn, state sync, movement, aim, weapons, fire, projectiles,
damage, chat, disconnect — remain undocumented and are classified UNKNOWN until
captured.

## The core Bot

The core Bot keeps the event-driven design from earlier rounds (`on`/`once`/`emit`,
async-friendly, capability gates on unsupported actions) but its target changes:

- `connect()` performs the Mini Militia LAN handshake when the protocol is known —
  until then it raises `CapabilityError` and points at the research document.
- `join_lobby()`, `spawn`/`player_join`/`player_leave` events, `nearest_enemy()`,
  `aim_at()`, `fire()` all exist as the stable API surface; they dispatch through
  the LAN packet codec once packets are validated.
- A simulator (`SimAdapter`) remains for testing the bot's logic offline, and is
  explicitly labeled a stand-in — simulator tests are never counted as Mini
  Militia interoperability.

## Verification discipline

Nothing in the core claims game interoperability without a recorded pcap showing
the round-trip. The honest workflow for every new message type is: capture →
tag the in-game action → probe → hypothesize → round-trip validate → only then
move the claim from OBSERVED toward "supported". Until that pipeline produces
results, the core SDK is a ready API with an honest UNKNOWN codec.
