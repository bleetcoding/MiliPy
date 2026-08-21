# MiliPy

A programmable control and observation framework for a normal Mini Militia Android client, built around a local Android bridge.

MiliPy lets you write Mini Militia bots in Python against a clean, event-driven API. The bot never speaks Mini Militia's LAN game protocol directly. Instead, a small Kotlin Android app — the **MiliPy Bridge** — runs on the controlled device, captures its screen through Android's legitimate `MediaProjection` API, and dispatches touch gestures through an Android accessibility service. The Python SDK talks to the bridge over a versioned WebSocket protocol.

```
Python MiliPy SDK
        ↕  WebSocket (v1)
MiliPy Android Bridge (Kotlin)
        ↕  MediaProjection / AccessibilityService
Mini Militia (a normal, unmodified Android client)
```

The game itself still handles LAN discovery, lobbies, game networking, rules, and match lifecycle. MiliPy handles observation, player state, input, actions, events, and your automation logic. MiliPy is **not** a replacement Mini Militia server, **not** a fake network client, and **not** an RL agent.

## Quick start

Install the SDK:

```bash
pip install -e sdk
```

Write your first bot:

```python
from milipy import Bot

bot = Bot(host="192.168.43.1", port=8765)

@bot.on("ready")
def ready():
    print("Bot has spawned")

@bot.on("player_seen")
def enemy(player):
    print("Enemy:", player.name)

@bot.on("tick")
def tick(state):
    enemy = bot.nearest_enemy()
    if enemy:
        bot.aim_at(enemy)
        bot.fire()

bot.connect()
bot.run()
```

> **Important:** `host` is the address of the **MiliPy Android Bridge**, not a Mini Militia game server. It is referred to as the *MiliPy Bridge connection* throughout this project.

## Repository layout

```
milipy/
├── sdk/            # Python SDK (milipy package, tests, simulator)
├── bridge/         # Kotlin Android bridge app (AGP project)
├── protocol/       # Versioned protocol specification
├── docs/           # Architecture, topology, and roadmap docs
├── examples/       # Example bots
└── PROJECT_STATE.md
```

## What version 0.1 actually supports

| Feature | Status | Backing mechanism |
|---|---|---|
| Protocol v1 (JSON over WebSocket) | Supported | `sdk/src/milipy/protocol.py` + `bridge/.../Protocol.kt` |
| Python SDK (`Bot`, events, state, actions) | Supported | `sdk/src/milipy/` |
| Connection, pairing, capability negotiation | Supported | `hello`/`auth` handshake, constant-time pairing token |
| Screen observation | Supported (consent-gated) | `MediaProjection` → `VirtualDisplay` → `ImageReader` → base64 JPEG |
| Movement input | Supported (consent-gated) | AccessibilityService `dispatchGesture` joystick holds |
| Jump / crouch / punch (tap actions) | Supported (consent-gated) | AccessibilityService taps |
| Aim (drag to normalized point) | Supported (consent-gated) | AccessibilityService swipe |
| Fire / stop fire | Supported (consent-gated) | Touch hold on fire zone |
| Game session state (`NO_GAME` … `IN_GAME`, `UNKNOWN`) | Honest baseline only | `UNKNOWN` until a perception layer exists |
| Simulated mode (no phone needed) | Supported | `SimAdapter` — drives all SDK tests |
| Grenade, pickup, weapon switch, chat, player tracking/stats | **Unsupported** | Raises `CapabilityError` with `unsupported_capability` |

The rule for every missing feature is the same: when a capability cannot currently be implemented legitimately, the SDK raises a meaningful `CapabilityError` instead of pretending. Nothing in the bridge prints success for work that was not done.

## Both network topologies

The controlled device may be either the Mini Militia host or a client that joins a host's LAN lobby. Neither assumption is hard-coded.

**Bridge on the host phone:**

```
Host Phone
├── Wi-Fi hotspot
├── Mini Militia (host)
└── MiliPy Bridge (port 8765)

Termux / bot device ── on the same LAN ──▶ MiliPy SDK
```

**Bridge on a client phone:**

```
Host Phone          Client Phone
├── Wi-Fi hotspot   ├── Mini Militia (client)
└── Mini Militia    └── MiliPy Bridge (port 8765)

Termux / bot device ── on the same LAN ──▶ MiliPy SDK
```

## Testing without a phone

The SDK ships a simulator that implements the bridge protocol in memory, so the entire bot API can be exercised offline:

```bash
cd sdk && python3 -m pytest   # 121 tests
python3 tests/smoke.py        # end-to-end demo against SimAdapter
```

Version **0.2.0** adds the protocol v1.1 extension (action ids with structured `ack` replies and `status: accepted|rejected`, rich capability states distinguishing *available* from *unavailable* mechanisms), coordinate calibration across screen and game spaces (`milipy.coords`), perception-architecture interfaces (`FrameSource` → `PerceptionProvider` → `GameStateProvider` with an honest baseline that never fabricates detections), and per-device frame-rate / JPEG-quality tuning with latest-frame backpressure.

Version **0.3.0** makes the bridge a **foreground service** that owns the WebSocket listener for the app's entire lifetime — closing the UI no longer kills the bridge, and a persistent **"MiliPy Bridge — Running"** notification offers an explicit **Stop Bridge** action. Remote shutdown is also available as the `stop_bridge` protocol action (`await bot.stop_bridge_async()`). Capability flags are now re-evaluated from live runtime state on every handshake: `gesture_input` requires the accessibility service to be enabled *and* bound, `screen_capture` requires a live MediaProjection session, and a revoked capture session is reported immediately through the `capture_stopped` event. See [`docs/service-persistence.md`](docs/service-persistence.md) for the full design.

## Docs and roadmap

See [`docs/architecture.md`](docs/architecture.md) for the two-networking separation, [`protocol/protocol.md`](protocol/protocol.md) for the wire spec (v1.1), [`docs/termux.md`](docs/termux.md) for installing and running the SDK in Termux on Android, [`docs/device-validation.md`](docs/device-validation.md) for the validation matrix and what still needs real-device verification, [`docs/android-compatibility.md`](docs/android-compatibility.md) for platform requirements and OEM limitations, [`docs/service-persistence.md`](docs/service-persistence.md) for the v0.3.0 foreground-service lifetime, and [`docs/roadmap.md`](docs/roadmap.md) for the v0.2–v1.0 plan. The debug bridge APK is attached to the [v0.1.0 release](https://github.com/bleetcoding/MiliPy/releases).

## License

[MIT](LICENSE)
