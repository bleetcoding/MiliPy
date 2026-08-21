# Mineflayer Research Notes (Round 5)

## What Mineflayer is
Mineflayer (PrismarineJS, GitHub 7.3k stars, MIT, since 2011) is a JavaScript framework
for creating Minecraft bots with a high-level, stable, event-driven API, also usable
from Python via the node-minecraft-protocol Python binding (python-mineflayer exists
via npm-to-python interop; the user's syntax `from milipy import Bot` matches this style).

## How Mineflayer works (the architecture to emulate)
1. **Standalone client, direct protocol.** `mineflayer.createBot({host, port, username})`
   connects *directly* to the Minecraft server over TCP and speaks the real Minecraft
   protocol. There is NO screen capture, NO injected client, NO device automation. The
   bot IS a client indistinguishable (at the protocol level) from a real player.
2. **Layered module stack:**
   - `node-minecraft-protocol` — packet parsing/serialization, auth, encryption, keep-alive.
     `client.write('packet_name', {fields})`, `client.on('packet_name', cb)`.
   - `minecraft-data` — language-independent data repo (packet definitions per version,
     block/entity/item definitions), so bots adapt per game version.
   - `prismarine-*` modules (physics, chunk, block, entity, world, windows, item, biome)
     — domain objects built from incoming packets.
   - `mineflayer` — the high-level Bot: world model maintained server-authoritative,
     entity tracking (players/entities arrays), events: `spawn` (bot spawned in world),
     `player_join`/`player_leave`, `chat`, `kicked`, `error`, `death`, `message`.
3. **Server-authoritative world model.** The bot maintains a local mirror of the world
   populated by server packets: position updates, entity spawn/despawn, inventory, chat.
   The bot never guesses; the server is the source of truth.
4. **High-level verbs from low-level packets.** `bot.chat(msg)` → Chat packet;
   `bot.lookAt(point)` → Player Position packet; plugins add `mineflayer-pvp`,
   `mineflayer-pathfinder` etc.
5. **Event-driven async** (Node.js). Python port uses asyncio; mineflayer Python examples
   exist on Google Colab (docs/mineflayer.ipynb).
6. **Testing without a server:** the whole stack is unit-testable against a local server
   and has a fake/mock protocol for tests; debug via `DEBUG=minecraft-protocol`.
7. **Plugins.** Anything added later is a plugin on top of the Bot; core stays small.

## Target MiliPy API (from user; mineflayer-like)
```python
from milipy import Bot
bot = Bot("192.168.1.x")
bot.on("spawn", ...)
bot.on("player_join", ...)
bot.on("player_leave", ...)
bot.connect()
bot.join_lobby()
target = bot.nearest_enemy()
bot.aim_at(target)
bot.fire()
bot.disconnect()
```

## Key translation to MiliPy
- `minecraft-protocol` layer  → future `milipy/mm_protocol` (packet codec)
- `minecraft-data` layer      → future `milipy/mm_data` (packet definitions, per-MM-version)
- mineflayer Bot              → existing Bot class (already event-driven) retargeted at LAN
- The honest baseline: until packets are verified against a real host, the protocol
  module MUST be labeled UNKNOWN/OBSERVED, never "supported".

## Sources
- https://github.com/PrismarineJS/mineflayer
- https://github.com/PrismarineJS/node-minecraft-protocol
- https://prismarinejs.github.io/node-minecraft-protocol/
- https://wiki.vg/Protocol (Minecraft protocol wiki)
