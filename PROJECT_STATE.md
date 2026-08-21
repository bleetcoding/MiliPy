# MiliPy Project State (working notes — not deliverable content)

## User task (summary of /home/ubuntu/upload/pasted_content.txt and pasted_content_2.txt)
Build "MiliPy" — a Mineflayer-inspired game automation framework for Mini Militia.
- Python SDK (developer-facing, ergonomic: `Bot`, `bot.on`, `bot.connect()`, `bot.run()`)
- Kotlin Android bridge (WebSocket server, MediaProjection capture, AccessibilityService gesture input)
- Versioned local WebSocket protocol (protocol 1, JSON). No cloud, no internet at runtime, offline/hotspot.
- No RL/AI/ML in core. No fake functions. Capability reporting. Unsupported actions raise UnsupportedCapabilityError.
- Simulator (milipy.sim.SimAdapter) for CI/testing.
- Serious tests with pytest; Kotlin unit tests. Tests must not depend on Mini Militia.
- Docs: README (status matrix ✅/🟡/🔴), docs/ (architecture, protocol, android-setup, termux-setup, bot-api), CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, LICENSE (MIT), ROADMAP (v0.1→v1.0 as in brief §38).
- GitHub: repo name "MiliPy", determine authenticated owner via `gh api user`, initial commit to main, no secrets/tokens/IPs. CI via GitHub Actions (Python pytest+lint; Android compile).
- Deliver: complete repo + final report: what was tested, what remains unsupported.
- Deliverable dev experience: `from milipy import Bot; bot = Bot("192.168.43.1"); ... bot.connect(); bot.run()`

## Repository structure (final)
MiliPy/ monorepo:
- sdk/          → Python package (src layout: sdk/src/milipy), pyproject.toml, tests/
- android/      → Kotlin Gradle project MiliPyBridge (app/)
- protocol/     → README.md + protocol.md + schema/json files + examples/
- examples/     → basic_bot.py, movement_bot.py, tracking_bot.py, combat_demo.py, sim_demo.py
- docs/         → architecture.md, android-setup.md, termux-setup.md, bot-api.md, roadmap.md
- simulator/    → (docs/examples via sim_demo.py; SimAdapter in sdk)
- .github/workflows → ci-python.yml, ci-android.yml
- README.md, LICENSE, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, .gitignore

## Protocol decisions (see protocol/protocol.md — ALREADY WRITTEN)
- type field mandatory; hello/hello_ack/auth_required/auth/auth_error/protocol_error/state/event/error/ack/result/action envelopes.
- Pairing: 6-char alphanumeric token, constant-time compare.
- Capabilities: screen_capture, gesture_input, player_tracking, chat, settings_read, settings_write.
- v0.1 supported: connection, handshake/auth, capabilities, screen capture (MediaProjection), movement hold actions (move/stop/set_control), jump/crouch taps, aim/aim_at (normalized nx,ny), fire/stop_fire.
- v0.1 UNSUPPORTED (raise UnsupportedCapabilityError / unsupported_capability error): punch, throw_grenade, pickup, switch_weapon, chat_send, player stats, game settings write.

## Android bridge decisions (research notes.md)
- Ktor server (CIO engine) + ktor-websockets on Android. Kotlin 1.9.24, AGP 8.x, compileSdk 34, targetSdk 34, minSdk 26.
- Screen: MediaProjectionManager.createScreenCaptureIntent → foreground service (FOREGROUND_SERVICE_MEDIA_PROJECTION) → ImageReader → JPEG base64 frames.
- Input: AccessibilityService with canPerformGestures="true", dispatchGesture for taps/swipes (aim = hold joystick stroke; fire = tap fire button region). Requires explicit user Accessibility permission + consent UI.
- Pairing code displayed in bridge UI activity; entered by client.

## Python SDK decisions
- asyncio + websockets library. Bot class with EventEmitter (on/once/off), state machine (disconnected→connecting→authenticating→ready), periodic state via on("state"), events mapped from protocol events.
- Models: Player (id, name, position Position(nx,ny), velocity optional, health, max_health, weapon, team, alive), Vector, Weapon (id, name, ammo, max_ammo, equipped), State (tick, timestamp, player, players, frame optional), Capabilities, ChatMessage.
- bot.player, bot.players, bot.entities, bot.weapons, bot.state, bot.chat, bot.settings; nearest_player(), nearest_enemy().
- SimAdapter in milipy.sim — implements same adapter contract as real WebSocket transport, runs tiny in-process fake bridge.

## Research findings
- Mini Militia: NO official API exists (Appsomniacs/Miniclip; Wikipedia https://en.wikipedia.org/wiki/Mini_Militia, Play Store pages). External bridge architecture is the only legitimate path.
- MediaProjection docs: https://developer.android.com/media/grow/media-projection
- AccessibilityService docs: https://developer.android.com/guide/topics/ui/accessibility/service
- Ktor websockets: https://ktor.io/docs/server-websockets.html

## Status / TODO
- [x] Phase 1 research
- [x] Protocol spec written (protocol/protocol.md)
- [ ] Phase 3: Python SDK implementation
- [ ] Phase 4: Kotlin bridge (build with Gradle in sandbox; install Android cmdline-tools + sdkmanager)
- [ ] Phase 5: Simulator + pytest suite, CI
- [ ] Phase 6: Docs, examples, metadata
- [ ] Phase 7: gh auth check (gh api user), create repo MiliPy (private default? brief says public repository), push, final report

## Environment notes
- GitHub CLI pre-authenticated. Check owner: `gh api user --jq .login`
- Sandbox: Ubuntu 24.04, Python 3.11, Node 22, pnpm. No Android SDK yet — must install cmdline-tools.


## Progress log (updated)
- [x] Phase 3 nearly complete: SDK implemented under /home/ubuntu/milipy/sdk (src/milipy: __init__, bot, client(not used—transport instead), protocol, protocol_schema, events, actions, state, transport, sim). pyproject.toml done. Installed editable with pytest-asyncio, ruff, websockets.
- Smoke test (tests/smoke.py) passes; Bot+SimAdapter full cycle works (move right observed, player_seen x2, nearest_enemy, CapabilityError, ValueError aim_at ghost).
- pytest suite: tests/test_protocol.py, test_state_events.py, test_sim_bot.py. Fixing last failures: sim.py await _on_frame→_notify fixed; remaining: TestRealWebSocketHandshake::test_connect_completes_handshake fails because server never receives hello (asyncio.sleep(0) sync lambda returns coroutine; adapter._handle_incoming awaits it; server handler reads raw frames — need sleep after connect to let hello flush). Also test_unsupported_action_raises may pass now.
- Remaining phases: 4 Kotlin bridge (need Android SDK cmdline-tools install; AGP/Ktor build), 5 tests green + CI, 6 docs/examples/README/LICENSE/CONTRIBUTING/SECURITY/CODE_OF_CONDUCT/ROADMAP, 7 gh api user to get owner; repo name "MiliPy" public; push main; final report.
- Note: bot.py imports transport.Bot references _async_connect; smoke test pattern works via connect_async.
- Examples to write: examples/basic_bot.py, movement_bot.py, tracking_bot.py, combat_demo.py, sim_demo.py
- Protocol doc done: /home/ubuntu/milipy/protocol/protocol.md


## Phase 4 (architecture correction) — COMPLETE
User correction applied (do NOT rebuild): (1) Bot host = MiliPy Bridge address, never the game server; documented in bot.py docstring, __init__.py, protocol.md §1.1. (2) Added GameSession enum (NONE/UNKNOWN/MAIN_MENU/LAN_MENU/LOBBY_VISIBLE/IN_LOBBY/IN_GAME/GAME_OVER) to state.py, GameState.game_session field, bot.game_session property, parser in bot._apply_state, sim reports UNKNOWN honestly. (3) protocol.md now has §1.1 two-networking-layers table, §1.2 topologies A (bridge on host phone) and B (bridge on client phone), device info block in hello_ack, game_session in state message, §8 game session observation (honest baseline unknown). (4) Tests added: test_game_session_observed, test_punch_raises_when_gesture_input_unavailable; test_unsupported_action_raises adjusted (punch needs gesture_input=available). All 84 tests passing; smoke passes. (5) Git initialized at /home/ubuntu/milipy with commit a5a235c.

## Phase 5 (Kotlin bridge) — IN PROGRESS
TODO: install Android cmdline-tools + AGP 8.x + Ktor, build app under bridge/. Bridge: WebSocket server port 8765, hello/auth handshake, state observations at tick interval, action handling (move/stop/aim/fire...), capability report, pairing token, game_session=UNKNOWN honest baseline, device info in hello_ack, accessibility service gestures (AccessibilityNodeInfo dispatch + ACTION_INJECT gesture via AccessibilityService), MediaProjection screen capture (documented, requires user consent), package com.milipy.bridge. Must compile with gradle (offline-friendly: use AGP version available; fallback: at minimum a self-contained Kotlin build with Ktor via gradle).
Then: phase 6 docs (README with architecture/topologies, architecture.md, docs/testing-local-network.md, SECURITY/CODE_OF_CONDUCT/CONTRIBUTING/LICENSE Apache-2.0, ROADMAP.md), examples (basic_bot.py, movement_bot.py, tracking_bot.py, combat_demo.py, sim_demo.py), CI (.github/workflows/ci.yml: python tests + kotlinc check), gh user → push to GitHub as "MiliPy" (public? original brief said publish to GitHub, public makes sense). Final report: what tested vs unsupported.


## Phase 5 details (in progress)
- Android SDK installed at ~/android-sdk (cmdline-tools 11076708 latest, platforms 34, platform-tools, build-tools 34.0.0). JDK 21 available. No kotlinc; using Gradle build.
- Bridge project at /home/ubuntu/milipy/bridge: settings.gradle.kts (rootProject MiliPyBridge, include :app), build.gradle.kts (AGP 8.7.3, Kotlin 1.9.25), app/build.gradle.kts (com.android.application, namespace com.milipy.bridge, minSdk 26/target/compile 34, JVM 17, deps: androidx.core-ktx 1.13.1, ktor-server-core/cio/websockets 2.3.12, org.json 20240303). local.properties points sdk.dir=/home/ubuntu/android-sdk.
- Manifest: INTERNET, ACCESS_NETWORK_STATE, FOREGROUND_SERVICE, FOREGROUND_SERVICE_MEDIA_PROJECTION, POST_NOTIFICATIONS; MainActivity exported launcher; MiliPyService (foregroundServiceType mediaProjection, not exported); MiliPyAccessibilityService (BIND_ACCESSIBILITY_SERVICE, canPerformGestures=true, config xml/accessibility_service_config.xml).
- Resources: strings.xml (app name "MiliPy Bridge", accessibility_description, notification strings), colors.xml (#1B2838 bg), mipmap-anydpi-v26/ic_launcher.xml + drawable/ic_launcher_foreground.xml (green diamond vector).
- Kotlin sources so far: Protocol.kt (all protocol constants + ACTION_CAPABILITIES map + GameSessionState enum), WorldState.kt (tick counter, move/aim/fire/control state, snapshot() producing state message with game_session=UNKNOWN honest baseline).
- Still to write: MainActivity.kt (pairing UI, start service, MediaProjection consent flow), MiliPyService.kt (Ktor CIO websocket server on 0.0.0.0:8765 bound, hello/auth handshake, tick loop pushing state via WorldState.snapshot, action dispatch table w/ capability check + unsupported error, ack, malformed error, capture toggle, disconnect), MiliPyAccessibilityService.kt (register global + dispatchGesture helpers for tap/swipe/hold), capture pipeline MediaProjectionService (foreground service + VirtualDisplay -> ImageReader; mark capabilities.screen_capture true when running).
- Build command: cd bridge && ANDROID_HOME=$HOME/android-sdk ./gradlew assembleDebug (gradle wrapper will download; AGP 8.7.3 needs gradle 8.9; check gradle/wrapper/gradle-wrapper.properties; must create gradlew via wrapper task — use gradle wrapper or download distribution directly). Alternative: install gradle 8.9 via sdkman.
- Tests for Kotlin: kotlinc not installed; validate via `./gradlew compileDebugJavaWithJavac`-equivalent; better run `./gradlew assembleDebug` which compiles everything. Optional lint.
- After bridge compiles: Phase 6 docs+examples+repo metadata, Phase 7 push to GitHub "MiliPy" + final report.
- Python side fully done (84 tests green, smoke green).


## Follow-up task (user request): make repo public + Termux run guide
- Repo bleetcoding/MiliPy made PUBLIC via `gh repo edit --visibility public --accept-visibility-change-consequences` — verified: `"private": false`. URL: https://github.com/bleetcoding/MiliPy
- SDK deps: websockets>=12.0 (import websockets.asyncio.client), requires-python >=3.10, setuptools wheel. Dev deps: pytest, pytest-asyncio, ruff. These are all plain pip packages, installable in Termux (`pkg install python` then pip install).
- Termux notes for guide: Termux python 3.10+ (check current: python3.11/3.12); pkg install python git clang build-essential (websockets has C dep? it uses no C ext, pure wheels mostly fine); use `pkg install python-websockets` OR pip install websockets; recommend pip. git clone into $HOME; cd milipy && pip install -e sdk.
- Real-network run: bridge runs on same phone or another phone; on same phone localhost 127.0.0.1:8765 works (bridge binds 0.0.0.0). Pairing token from app UI. env vars: MILIPY_HOST, MILIPY_PORT, MILIPY_PAIRING.
- Still to do: (1) write docs/termux.md guide, (2) mention in README, (3) commit+push, (4) deliver instructions to user.
