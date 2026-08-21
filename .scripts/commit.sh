#!/usr/bin/env bash
# Commit + push for round 4 (foreground service persistence, honest capabilities)
set -e
cd /home/ubuntu/milipy
git add -A
git -c user.name="MiliPy CI" -c user.email="ci@milipy.local" commit -q -m "v0.3.0: foreground-service bridge lifetime, honest runtime capability detection, stop_bridge action

- Bridge runs in a foreground service (mediaProjection type, START_STICKY)
  that owns the WebSocket listener; closing the activity no longer kills
  the bridge. Pairing config persists across restarts.
- Persistent 'MiliPy Bridge - Running' notification with Stop Bridge action.
- New protocol action stop_bridge (pairing-token-gated, no capability gate)
  with SDK bot.stop_bridge_async() and action builder method; simulator
  mirrors the teardown.
- Capabilities re-evaluated from live runtime state on every hello_ack:
  gesture_input requires accessibility service enabled AND bound;
  screen_capture requires a live MediaProjection session; revoked capture
  is reported via capture_stopped. Rich states include permission_required.
- Kotlin: 0.3.0 (versionCode 3); Python SDK/pyproject 0.3.0.
- Docs: service-persistence.md, protocol.md 2.5/4.8/7.1, testing.md
  persistence steps, device-validation.md rows, README v0.3.0 note.
- Tests: 121 passing (added tests/test_service_lifecycle.py)."
git push -q origin main
git log -1 --format="%H %s"
