# MiliPy Architecture

## What MiliPy is

MiliPy is a programmable control/observation framework for a **normal, unmodified Mini Militia Android client**, mediated by a local Android bridge app. It is deliberately not a replacement Mini Militia server, not a fake network client, and not an RL agent. The game retains full responsibility for LAN discovery, lobbies, game networking, rules, and match lifecycle. MiliPy is responsible for observation, player state, input, actions, events, and automation logic.

## Two completely separate networking concepts

MiliPy operates over two networking layers that must never be conflated.

### 1. Mini Militia LAN networking (not ours)

Mini Militia's multiplayer uses a Wi-Fi/LAN lobby workflow: one device hosts a hotspot, other devices join the hotspot, and the game discovers and joins lobbies itself. MiliPy does not implement, emulate, reverse-engineer, or manipulate any part of this protocol. The user performs the ordinary workflow by hand:

```
Host device:      enable hotspot → launch Mini Militia → host LAN game
Other devices:    connect to hotspot → launch Mini Militia → join lobby
```

### 2. MiliPy control networking (ours)

MiliPy's own, fully documented WebSocket protocol runs on top of the same local network but connects only Python-to-bridge:

```
Python MiliPy SDK
        ↕  WebSocket (port 8765 by default)
MiliPy Android Bridge
        ↕  Android observation/input layer
Mini Militia application
```

The bridge controls and observes the Mini Militia application exclusively through legitimate Android mechanisms — `MediaProjection` for screen capture and the Accessibility Service `dispatchGesture()` API for input — each behind an explicit user consent flow.

## The `host` parameter

```python
bot = Bot(host="192.168.43.1", port=8765)
```

The `host` argument is the address of the **MiliPy Android Bridge**, never the Mini Militia game server. MiliPy never exposes a function such as `connect_to_mini_militia_game_server()`. Calling `bot.connect()` is a *MiliPy Bridge connection*.

## Both supported topologies

The MiliPy-controlled device may be either the Mini Militia host or a Mini Militia client that joins a host's LAN lobby. Neither topology is hard-coded; the bridge simply binds to all local interfaces on its port.

**Topology A — bridge on the host phone:**

```
Host Phone
├── Android Wi-Fi hotspot
├── Mini Militia (LAN host)
└── MiliPy Bridge (port 8765)

Termux / bot device (on the same LAN)
└── Python MiliPy SDK ──────▶ 192.168.43.1:8765
```

**Topology B — bridge on a client phone:**

```
Host Phone
├── Android Wi-Fi hotspot
└── Mini Militia (LAN host)

Client Phone (on hotspot)
├── Mini Militia (client, joined the lobby)
└── MiliPy Bridge (port 8765)

Termux / bot device (on the same LAN)
└── Python MiliPy SDK ──────▶ <client-phone-IP>:8765
```

For the first working prototype, Topology B is usually technically easier because the bridge phone only needs to *join* a hotspot rather than host one, and its IP is simply whatever the hotspot DHCP assigns. Topology A remains equally valid once the bridge can run as a background service on the host device.

## Android bridge responsibilities

The Kotlin bridge is responsible for Android lifecycle, screen capture, input abstraction, game-screen observation, the MiliPy WebSocket server, protocol handling, pairing/authentication, capability reporting, and logging. It is explicitly **not** responsible for pretending to be a Mini Militia server.

| Responsibility | Mechanism |
|---|---|
| Android lifecycle | Foreground `Service` with notification |
| Screen capture | `MediaProjectionManager.createScreenCaptureIntent()` → `MediaProjection.createVirtualDisplay()` → `ImageReader`, user consented |
| Input | `AccessibilityService.dispatchGesture()` (taps, swipes, sustained drags) — user must enable the service in system settings |
| WebSocket server | Ktor CIO, bound to `0.0.0.0:8765` |
| Protocol | JSON envelopes per `protocol/protocol.md` |
| Pairing | Displayed 6-character token, constant-time comparison, per-connection |
| Capabilities | Honest flags in `hello_ack` — `screen_capture` true only while a projection is active; `gesture_input` true only while the accessibility service is enabled |

## Capability honesty

Every feature that cannot currently be backed by a legitimate mechanism is reported as unavailable and raises `CapabilityError` on use. Version 0.1's honest baseline:

| Capability | Baseline |
|---|---|
| `screen_capture` | Available when MediaProjection consent was granted |
| `gesture_input` | Available when the user enabled the accessibility service |
| `player_tracking`, `chat`, `grenades`, `pickup`, `weapon_switch` | Unavailable — will raise `CapabilityError` until a perception layer exists |
| `settings_read`, `settings_write` | Available for bridge settings only (game settings untouched) |

## Game session state

The bridge and SDK model the visible game session with a small state enum: `NO_GAME`, `GAME_DETECTED`, `MAIN_MENU`, `LAN_MENU`, `LOBBY_VISIBLE`, `IN_LOBBY`, `IN_GAME`, `GAME_OVER`, and `UNKNOWN`. Version 0.1 reports `UNKNOWN` everywhere. This is intentional: the states will only become truthful once a perception layer (image analysis of the captured frames) can actually distinguish them. The abstraction exists now so future detection work plugs into a defined surface instead of inventing one.

LAN lobby discovery (`bot.lan_lobbies` / `bot.game.lobby`) will only ever be added if the bridge can legitimately obtain it from the application's visible UI or state — never by querying Mini Militia's internal LAN mechanism.

## The vertical slice (first real integration test)

1. Android device enables its hotspot (Topology A) or joins one (Topology B).
2. Mini Militia starts normally; host or client joins the LAN lobby normally.
3. The MiliPy Bridge is started on the controlled device.
4. Termux on the same local network connects to the MiliPy Bridge.
5. The bridge reports its connection status, Android device information, capabilities, and game detection status.
6. MiliPy receives a screen observation.
7. MiliPy sends a supported action; the bridge performs it through a legitimate Android mechanism; the result is visible.

Steps 4–7 are exercised offline by the SDK's `SimAdapter` simulator and its 84 tests; steps 1–3 happen on real hardware and are documented in [`testing.md`](testing.md).

## Engineering rule

Whenever a capability cannot currently be implemented legitimately: research → determine the limitation → design the abstraction → mark it unsupported → continue implementing everything else. Nothing prints success for work that was not done.
