# MiliPy Roadmap

The roadmap grows capability-by-capability, each step behind the project's
honesty model (`KNOWN` / `OBSERVED` / `INFERRED` / `UNKNOWN`) and its
capability gates. Version numbers describe maturity, not promises.

The core project is a **Mineflayer-style standalone Mini Militia LAN client**:
the Python bot speaks Mini Militia's LAN multiplayer protocol directly from
Termux and appears as an ordinary LAN client/player. The Android screen-
automation bridge is retained as an optional, experimental component
(`experimental/bridge/`) while the LAN client becomes the primary path.

## Current — research foundation (v0.3)

The Mineflayer-style Bot API (`on("spawn")`, `on("player_join")`,
`nearest_enemy()`, `aim_at()`, `fire()`, `connect()` / `join_lobby()` /
`disconnect()`), the honesty-gated codec (connecting to a raw LAN host raises
`CapabilityError` until packet formats are validated), the simulator
(labeled stand-in for offline testing), and the protocol research layer
(`protocol/lan-protocol-research.md` plus the capture/replay framework in
`protocol/research/`) are all implemented and tested offline.

## Next — packet capture and discovery

The first real interoperability milestone. Capture LAN traffic while performing
tagged in-game actions, identify the host's discovery port and any broadcast
mechanism, and promote the discovery/lobby areas from `UNKNOWN` toward
`OBSERVED` (see the capture steps A–G in the research document).

## Then — handshake, lobby join, and spawn

With discovery in hand, decode the host/client handshake, lobby join, player
identity/session, and spawn messages, validate each by send/receive
round-trip against a real Mini Militia LAN host, and let the simulator's
`spawn` / `player_join` / `player_leave` events map to the real protocol's
events. The first `Bot("192.168.43.x").connect()` against a real host is the
project's defining moment — it is only claimed after the pcap proves it.

## Then — gameplay state and combat

Player state synchronization, position/movement, aim/orientation, weapon
selection, fire/actions, projectile and grenade events, and damage/death state
follow the same capture → probe → round-trip discipline. Chat is included if
the protocol exposes it; if captures show no chat channel exists, the honest
answer is that it does not.

## v1.0 — standalone client

Declaring 1.0 happens only after the Bot connects, joins, plays, and
disconnects cleanly against real Mini Militia LAN hosts across multiple game
versions, devices, and both hotspot topologies, with every message type backed
by recorded captures and passing replay tests. No artificial timeline.

## About the experimental bridge

The Android bridge retains its own roadmap (perception layer, combat actions,
metagame, platform stability) but is explicitly optional: it automates a
screen rather than speaking the game protocol, and nothing in the core bot
depends on it. Contributions may pursue either path; the core client is the
primary project direction.
