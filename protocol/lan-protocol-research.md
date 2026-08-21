# Mini Militia LAN Protocol — Research Layer

> **Nothing in this document is a packet format.** Until MiliPy has captured and decoded
> real traffic against a Mini Militia LAN host, every wire-format claim in this
> repository is labeled with one of four certainty levels, and the code treats the
> protocol as *unknown*. This document is the research layer: it records what public
> sources establish, what we have actually captured, what we can reasonably infer, and
> what remains genuinely unknown — together with the capture/replay framework for
> turning UNKNOWN into OBSERVED.

## 1. Certainty model

Every claim about the Mini Militia LAN protocol is tagged with one of four levels, and the code must never act on a claim above the evidence.

| Level | Meaning |
|---|---|
| **KNOWN** | Established by multiple independent public sources (or by the game's own documentation). Safe to build on, though still subject to revision. |
| **OBSERVED** | Captured by MiliPy's own packet capture framework against a real LAN host. This is the gold standard; anything here is recorded evidence, not theory. **Currently the OBSERVED section is empty — no captures exist yet.** |
| **INFERRED** | A reasonable hypothesis from known facts (e.g., how Unity Android LAN games of the era typically behave). Must be tested against captures before the code trusts it. |
| **UNKNOWN** | No evidence exists. The research framework is designed to fill these gaps, not to guess. |

## 2. What is KNOWN (public sources)

The following is established by public documentation and community sources, searched and collected in August 2026.

**Game identity and topology.** Mini Militia — Doodle Army 2 (`com.appsomniacs.da2` on Google Play, Appsomniacs LLC) is a 2D multiplayer shooter supporting local Wi-Fi (LAN) multiplayer with multiple players per session [1] [2]. The LAN session is hosted by one player's phone: "one of the player hosts the game and all other players connect to that host" [3]. Host and clients must share a local network (the classic setup is a phone hotspot with everyone joined to it). No internet connection is required for LAN play — the session runs entirely on the local network [4].

**Transport.** Public sources describe the local multiplayer as using **UDP for low-latency gameplay** [4]. The authoritative confirmation of ports and packet structure requires capture (see §4).

**Server history (context, not protocol).** The game's online multiplayer originally ran on GameSpy infrastructure; the official servers shut down around 2018, multiplayer shutdown was announced October 1 2022 and completed March 26 2024 [5]. LAN play persists because it is host-driven and peer-to-peer-local — the host phone runs the game session itself. This is useful context: the LAN protocol is the *only* surviving multiplayer protocol of the game, and no official documentation for it was ever published.

**Absence of public packet documentation.** Extensive searching (packet format, reverse engineering, private server, emulator, protocol) returned **no** public write-ups, packet definitions, or working protocol implementations for Mini Militia's LAN mode [6]. This matters: any future claim of "Mini Militia protocol support" in MiliPy must be backed by MiliPy's own captures, because nobody else has published the answer.

| Fact | Source | Certainty |
|---|---|---|
| LAN multiplayer over local Wi-Fi/hotspot, no internet | [3] [4] | KNOWN |
| Host-client topology (one host, many clients) | [3] | KNOWN |
| UDP used for gameplay traffic | [4] | KNOWN (transport class; ports/modes unconfirmed) |
| Max LAN player counts vary by source (6–12) | [1] [2] | KNOWN (exact number may vary by game version) |
| Published packet formats | — | **Do not exist publicly** |
| Working LAN protocol implementations | — | **None found publicly** |

## 3. The 15 research areas

The user's research brief defines the protocol map. Each area is currently classified; the capture framework (§4) is designed to fill them.

| # | Area | Status | Notes |
|---|---|---|---|
| 1 | LAN host discovery | UNKNOWN | How does a client find the host? Likely UDP broadcast on a fixed port — INFERRED, untested. |
| 2 | LAN lobby discovery | UNKNOWN | The lobby list shown in-game; format unknown. |
| 3 | Host/client handshake | UNKNOWN | Including any session key, name exchange, game-version check. |
| 4 | Lobby join protocol | UNKNOWN | Join request/accept, slot assignment, game settings exchange. |
| 5 | Player identity/session | UNKNOWN | Player name, ID, session token. |
| 6 | Spawn messages | UNKNOWN | Spawn point, initial state. |
| 7 | Player state sync | UNKNOWN | Periodic state snapshots vs. delta updates. |
| 8 | Position/movement | UNKNOWN | Encoding of x/y, velocity, jetpack, direction. |
| 9 | Aim/orientation | UNKNOWN | Angle/aim encoding. |
| 10 | Weapon selection | UNKNOWN | Pickup, switch, ammo accounting. |
| 11 | Fire/action messages | UNKNOWN | Fire start/stop, punch, grenade throw. |
| 12 | Projectile/grenade events | UNKNOWN | Spawn, trajectory, detonation. |
| 13 | Damage/death/state events | UNKNOWN | Hit registration, respawn, kill feed. |
| 14 | Chat | UNKNOWN | Whether the LAN protocol exposes chat at all. |
| 15 | Clean disconnect | UNKNOWN | Leave protocol, host-end notification. |

## 4. Turning UNKNOWN into OBSERVED — capture framework

The `protocol/research/` directory ships a small, honest framework: `capture.py` (UDP packet logger + pcap recording), `analyze.py` (statistical structure probes on captured bytes), and `replay.py` (plays recorded captures into a test listener). The discipline it enforces:

1. **Capture.** On a Termux device (or any device on the LAN), run `capture.py` while the game performs a specific action (host a room, join a lobby, fire, move). Every packet is logged with timestamp, direction, length, and raw bytes, and written to a pcap for Wireshark cross-check. Root is not required: Android allows apps to open UDP sockets, and Termux's `pcapdump`/rootless approaches plus per-action capture windows suffice.
2. **Correlate.** Each capture run is tagged with the exact in-game action performed during the window. The framework never labels a packet "fire" because it looks like one; it labels it "captured during: fired at 12.3s".
3. **Probe.** `analyze.py` runs header-length histograms, entropy scans, periodicity detection, and broadcast-port sweeps on the captures. These are hypotheses generators, not decoders.
4. **Validate.** Any decoded field must round-trip: send a crafted packet via `replay.py`'s sender mode and confirm the game responds identically to the recorded reference. Until this round-trip passes, a format remains INFERRED, never KNOWN.

### Planned capture steps (in order)

| Step | Action | What it should reveal |
|---|---|---|
| A | Idle host + idle client on the same network, capture all UDP | Discovery traffic, heartbeat cadence, host port |
| B | Client browses lobby list | Lobby discovery packets |
| C | Client joins the room (stays in lobby) | Handshake + join protocol |
| D | Match starts, both players idle | Spawn + state sync baseline |
| E | One player moves/fires/jumps/grenades while the other is idle | Movement, fire, projectile deltas |
| F | Chat messages sent/received | Chat packets |
| G | Player leaves / host ends game | Disconnect protocol |

## 5. What MiliPy will NOT do

In line with the project's honesty rules, the protocol client must never: fabricate packet formats and call them "Mini Militia protocol"; claim support for any of the 15 areas from INFERRED evidence; or treat a replay test against MiliPy's own fake server as Mini Militia interoperability. The simulator used for unit tests is explicitly labeled as a stand-in, and real interop is only claimed after a capture round-trip against an actual Mini Militia LAN host.

## References

[1]: https://apps.apple.com/us/app/mini-militia-doodle-army-2/id405885221 "Mini Militia - Doodle Army 2 — App Store"
[2]: https://doodle-army-2-mini-militia.en.softonic.com/android "Doodle Army 2 : Mini Militia for Android — Softonic"
[3]: https://discussions.unity.com/t/android-mobile-local-multiplayer-game-via-wifi/178881 "Android mobile local multiplayer game via Wifi — Unity Discussions"
[4]: https://www.instagram.com/reel/DGNeM94yQwB/ "Mini Militia over Hotspot/WiFi — Instagram"
[5]: https://stopkillinggames.wiki.gg/wiki/Dead_game_list "Dead game list — Stop Killing Games Wiki"
[6]: https://github.com/lan-dot-party/game-protocols "Game Server Protocol Archive — lan-dot-party"

1. [Mini Militia — Doodle Army 2 (App Store)][1]
2. [Doodle Army 2: Mini Militia for Android (Softonic)][2]
3. [Android mobile local multiplayer game via Wifi (Unity Discussions)][3]
4. [Mini Militia over Hotspot/WiFi (Instagram)][4]
5. [Dead game list (Stop Killing Games Wiki)][5]
6. [Game Server Protocol Archive (lan-dot-party)][6]
