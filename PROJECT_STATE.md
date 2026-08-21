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
