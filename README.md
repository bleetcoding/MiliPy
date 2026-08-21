# MiliPy

A Mineflayer-style standalone client for Mini Militia, written in Python and designed to run entirely from Termux.

The core MiliPy bot speaks the **Mini Militia LAN multiplayer protocol directly**: it appears on the local network as an ordinary LAN client/player of a Mini Militia host, with no phone automation and no screen capture required. The event-driven API mirrors the shape Mineflayer gives Minecraft bots:

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

The project's engineering rule is radical honesty about the wire protocol: Mini Militia has **no published LAN protocol documentation** and no public implementation exists anywhere, so every packet-format claim is tagged `KNOWN` / `OBSERVED` / `INFERRED` / `UNKNOWN`, nothing is fabricated, and Mini Militia interoperability is never claimed until a capture round-trip against a real LAN host has proven it. Right now the LAN codec is `UNKNOWN` — `Bot("192.168.x.x")` raises a `CapabilityError` pointing at the research document instead of pretending, and the capture/replay framework exists to turn that into real `OBSERVED` evidence.

```
Termux
  |
  | Python MiliPy
  | Mini Militia LAN protocol (UDP)
  v
Mini Militia LAN host
```

## Quick start

Install the SDK and run the offline tests and simulator demo (no phone, no network, no Mini Militia):

```bash
git clone https://github.com/bleetcoding/MiliPy.git
cd MiliPy && pip install -e sdk
pip install pytest pytest-asyncio
cd sdk && python3 -m pytest      # all tests pass, zero network
python3 ../examples/first_bot.py --simulate
```

To help turn `UNKNOWN` into `OBSERVED`, capture real LAN traffic with the research tooling — see [`protocol/lan-protocol-research.md`](protocol/lan-protocol-research.md) and [`docs/termux.md`](docs/termux.md).

## Repository layout

```
milipy/
├── sdk/                     # Python SDK (milipy package, tests, simulator)
├── protocol/
│   ├── lan-protocol-research.md   # LAN protocol honesty model + public facts
│   ├── protocol.md                # Bridge wire spec (v1.1)
│   └── research/                  # capture.py / analyze.py / replay.py
├── docs/                    # Architecture, termux, roadmap docs
├── experimental/
│   ├── bridge/              # Optional Android bridge app (screen automation)
│   └── docs/                # Android-specific docs
├── examples/                # Example bots
└── PROJECT_STATE.md
```

## Two components, one honest core

| Component | Path | Role |
|---|---|---|
| **Core LAN client** | `sdk/` | Primary. Mineflayer-like Bot + honesty-gated LAN protocol client |
| **Android bridge** | `experimental/bridge/` | Optional experiment. Automates a screen via `MediaProjection` + Accessibility Service; its own WebSocket protocol lives in `protocol/protocol.md` |

The core bot never requires the bridge. The bridge predates the architecture correction and remains useful for screen-observation play, but it is explicitly optional and is not counted toward Mini Militia protocol support.

## What "supported" means in this project

| Level | Meaning |
|---|---|
| Tested offline (simulator) | The bot's logic works against MiliPy's own stand-in simulator — **not** Mini Militia interoperability |
| Mechanism-tested | An Android mechanism (e.g., MediaProjection) was exercised — still not game protocol |
| Mini Militia interoperability | A capture round-trip against a real LAN host — the only claim that counts |

| Feature | Status | Backing |
|---|---|---|
| Event-driven Bot API (`on`, `nearest_enemy`, `aim_at`, `fire`, …) | Implemented, simulator-tested | `sdk/src/milipy/` |
| Simulator (offline tests, no phone) | Supported | `SimAdapter` — explicitly labeled stand-in |
| Bridge WebSocket protocol (v1.1) | Implemented (bridge side compiles to APK) | `protocol/protocol.md` + `experimental/bridge/` |
| Foreground-service bridge lifetime, runtime capability checks, `stop_bridge` | Implemented (v0.3.0) | See v0.3.0 notes below |
| Coordinate calibration, perception interfaces | Implemented | `milipy.coords`, `milipy.perception` |
| **Mini Militia LAN packet codec** | **UNKNOWN — not implemented** | Raises `CapabilityError`; capture framework ready in `protocol/research/` |
| Grenade, pickup, weapon switch, chat, player tracking | Unsupported until codec is known | Raises `CapabilityError` |

The rule for every missing feature is the same: when a capability cannot currently be implemented legitimately, the SDK raises a meaningful `CapabilityError` instead of pretending. Nothing prints success for work that was not done.

## Version history

**v0.1.0 — v0.2.0** built the original architecture: the Python SDK, the bridge's WebSocket protocol (v1 and v1.1 — action ids with structured acks, rich capability states), coordinate calibration, perception interfaces, and the simulator. **v0.3.0** made the bridge a foreground service owning the WebSocket listener for the app's whole lifetime (closing the UI no longer kills it; a persistent notification offers **Stop Bridge**), added remote shutdown via the `stop_bridge` action, and re-evaluated capability flags from live runtime state (`gesture_input` requires the accessibility service enabled and bound; `screen_capture` requires a live MediaProjection session; revoked capture fires `capture_stopped`).

**v0.4.0 — this architecture correction.** MiliPy's true target is a Mineflayer-like standalone Mini Militia LAN client. The core Bot was retargeted at the LAN protocol, the honesty model (`KNOWN`/`OBSERVED`/`INFERRED`/`UNKNOWN`) was formalized in [`protocol/lan-protocol-research.md`](protocol/lan-protocol-research.md), the capture/replay research framework was added, and the Android bridge was moved to `experimental/bridge/` as an optional component. Connecting to a raw LAN host address now refuses honestly until packet captures promote the codec out of `UNKNOWN`.

## Docs and roadmap

See [`docs/architecture.md`](docs/architecture.md) for the full design, [`protocol/lan-protocol-research.md`](protocol/lan-protocol-research.md) for the LAN protocol evidence ledger, [`docs/termux.md`](docs/termux.md) for running from Termux, [`docs/roadmap.md`](docs/roadmap.md) for the path to v1.0, [`experimental/bridge/README.md`](experimental/bridge/README.md) for the optional bridge, and [`experimental/docs/`](experimental/docs/) for Android-specific documentation. The debug bridge APK is attached to the [v0.3.0 release](https://github.com/bleetcoding/MiliPy/releases/tag/v0.3.0).

## License

[MIT](LICENSE)
