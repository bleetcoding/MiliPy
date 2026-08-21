# MiliPy v0.1 — Build Report

Author: Manus AI · Date: August 21, 2026

This report describes what was actually implemented, built, and tested in this session, and what remains unsupported. It follows the project's standing rule: capabilities that cannot currently be implemented legitimately are marked unsupported and raise meaningful errors rather than being faked.

## What was implemented

The project is a monorepo containing a Python SDK (`sdk/`), a Kotlin Android bridge app (`bridge/`), a versioned protocol specification (`protocol/protocol.md`), documentation (`docs/`), and examples (`examples/`). The repository was initialized with Git, all work is committed, and everything was compiled and tested in this environment — nothing was declared working without evidence.

### Python SDK (built, installed, and tested)

The SDK provides the target developer experience: `Bot(host, port)` connects to the **MiliPy Android Bridge** — never to Mini Militia's game server, per the architecture correction in the brief. It ships a full event system (`ready`, `tick`, `player_seen`, `game_session`), state models (`Player`, `Position`, `Weapon`, `GameState`, `Capabilities`, `GameSession`), a complete actions API (movement holds, jump, crouch, aim, aim_at, fire, stop_fire, punch, capture control, settings), a `nearest_enemy()` query, and a protocol layer that validates every message against the v1 schema and raises `ProtocolError` / `CapabilityError` on violations. The SDK was installed with `pip install -e` and exercised end-to-end by a live smoke test and the full pytest suite.

### Kotlin Android bridge (built to a working APK)

The bridge app compiles to `app-debug.apk` with AGP 8.7.3 / Gradle 8.9 / Kotlin 1.9.25 and JDK 21 in this environment. It implements the full server side of the protocol: Ktor CIO WebSocket server on port 8765, the `hello`/`auth` handshake with a pairing token verified in constant time, capability reporting, a tick observation loop that pushes state at a configurable frame rate, action dispatch with capability gating, and honest error envelopes. Screen capture uses `MediaProjection` → `VirtualDisplay` → `ImageReader` with explicit user consent; input uses an accessibility service with `dispatchGesture()` (taps, swipes, sustained drags), enabled only via the system settings consent gate. The protocol constants in `Protocol.kt` were verified to exactly match the Python SDK's `protocol_schema.py`.

### Simulator

`SimAdapter` implements the bridge protocol in memory, driving a deterministic synthetic world. It runs every SDK capability offline — including honest `CapabilityError` for unsupported actions — and powers the entire test suite plus `examples/first_bot.py --simulate`.

### Documentation and repo metadata

The README, architecture document (two-networking separation and both hotspot topologies), testing guide, roadmap (v0.1–v1.0), MIT LICENSE, `.gitignore`, and a GitHub Actions CI workflow (SDK tests + bridge APK build + lint) are all in place.

## What was actually tested

| Evidence | Result |
|---|---|
| `python3 -m pytest` in `sdk/` | **84 tests passing** — protocol serialization and validation, event emitter, state models, simulator-driven bot integration (handshake, capability negotiation, actions, errors, game session) |
| `tests/smoke.py` | Live end-to-end cycle: handshake, state stream, movement, `player_seen` events, `nearest_enemy()`, `CapabilityError` for grenades, graceful rejection of actions lacking position data |
| `examples/first_bot.py --simulate` | Full developer-experience flow runs live against the simulator |
| `./gradlew assembleDebug` | APK builds from a clean compile (`compileDebugKotlin` green, AAPT and DEX stages green) |
| Protocol parity | Kotlin `Protocol.kt` constants match Python `protocol_schema.py` by inspection of the generated sources |

## What remains unsupported (honestly flagged)

| Item | Status |
|---|---|
| Grenade, pickup, weapon switch, punch-into-combat, chat | Raise `CapabilityError`; no perception layer exists yet to know where these targets are on screen |
| Player tracking beyond what observation events report | Simulator and event model support it; real detection awaits v0.2 perception |
| Truthful game session states (`MAIN_MENU`, `IN_LOBBY`, `IN_GAME`, …) | All report `UNKNOWN` until perception can distinguish them |
| LAN lobby discovery (`bot.lan_lobbies`) | Deliberately not implemented; will only be added if obtainable from visible UI |
| On-device integration test (the vertical slice) | Documented in `docs/testing.md`; requires a real Android phone and Mini Militia installation, which this environment does not have |
| Per-device gesture zone calibration | Zones are approximate 1280×720 values needing per-device tuning |

## What changed in this session

Per the architecture correction brief, the project was inspected and adapted rather than rebuilt. The SDK's separation from the bridge was already correct and was preserved. The `Bot` host documentation was corrected to name the MiliPy Bridge connection explicitly; a `GameSession` state model with an honest `UNKNOWN` baseline was added to the state model, protocol, simulator, and tests; the protocol spec gained an architecture section documenting the two-networking separation; the README and all documentation were written from scratch; the Kotlin bridge was implemented and compiled; and the repo was prepared for publication to the authenticated GitHub account (`bleetcoding/MiliPy`).
