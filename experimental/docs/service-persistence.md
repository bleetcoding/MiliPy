# MiliPy Bridge Service Persistence

Version **0.3.0** restructures the bridge's lifetime so that the bot keeps
working even when the app is no longer on screen.

## What changed

| Before (v0.1–v0.2) | After (v0.3.0) |
|---|---|
| The bridge ran inside a service started by the activity, but the activity was the practical lifetime owner; backgrounding the app could kill the listener | The bridge is a **foreground service** with `START_STICKY` and the `mediaProjection` service type; it is the true lifetime owner |
| No way to stop the bridge except force-stopping the app | Explicit stop: notification **Stop Bridge** action, a **Stop bridge** button in the UI, or the `stop_bridge` protocol action |
| Capability flags were cached promises from when the bridge last started | Capabilities are re-evaluated on every `hello_ack` from **live runtime state** |
| `gesture_input` could report `false` on a device where the accessibility service was enabled (service instance not bound) | `gesture_input` now requires both *enabled in system settings* **and** *bound to the running process* |

## How the lifetime works

1. **Start.** The user taps *Start bridge* in the app, which requests
   MediaProjection consent (the screen-capture gate) and then starts the
   foreground service. The service shows a persistent **"MiliPy Bridge —
   Running"** notification with the pairing code and a **Stop Bridge**
   action.
2. **Run.** The WebSocket listener lives entirely inside the service. The
   user can close the activity, switch to Mini Militia, lock the phone, or
   let Android reclaim the activity — the bridge keeps serving SDK clients
   on the local network.
3. **Recovery.** The service declares `START_STICKY`, so if Android kills
   the process for memory pressure it is recreated and the listener comes
   back up. Pairing config persists in the app's own `SharedPreferences`,
   so nothing is forgotten on restart.
4. **Kill is honest.** `MiliPyService.isRunning()` is written by the
   service itself (on creation and destruction). If Android kills the
   process, the flag and the notification disappear together — nothing can
   falsely report "running". This is deliberate: no battery whitelists, no
   wakelocks, no invisible activities. We do not fight Android's process
   management; we just make the common backgrounding case work.
5. **Stop.** Three equivalent paths all reach the same teardown: the
   notification action, the UI button, and the `stop_bridge` protocol
   action sent by any paired SDK client. The listener dies with the
   service, the notification is removed, and the UI reflects `STOPPED`.

## The `stop_bridge` action (protocol extension)

```json
{"type": "action", "id": "action-17", "action": "stop_bridge"}
→ {"type": "ack", "id": "action-17", "action": "stop_bridge", "status": "accepted"}
```

Authorization is the pairing token — every session is already
pairing-gated, so no capability gate applies. The SDK exposes
`bot.stop_bridge_async()` and the action builder's `stop_bridge()`. The
simulator implements the same teardown: its observation loop dies on
`stop_bridge`, exactly mirroring the real bridge.

## Honest capability detection

Capability flags are snapshots of **real device state at the moment of the
handshake**, never cached promises:

| Capability | True when | `permission_required` when |
|---|---|---|
| `gesture_input` | Accessibility service enabled in system settings **and** bound to the running service | Enabled in settings but the service has not bound yet (transient after start) |
| `screen_capture` | A live MediaProjection session is feeding the virtual display | The session was created earlier but has been revoked or not yet created |

A MediaProjection session can be revoked by the user or the system at any
time; the service registers a callback that tears capture down immediately
and pushes a `capture_stopped` protocol event so SDK clients do not wait
on frames that will never arrive.

## Root cause of `gesture_input: false` on real devices (v0.1–v0.2)

On earlier builds the accessibility service instance existed only while
the process that bound it was alive. Backgrounding the app killed that
process, so an enabled-but-unbound service honestly reported `false` — the
detection was right, the lifetime was wrong. The foreground service fixes
the lifetime (the instance now stays bound as long as the bridge runs),
and the settings-registry check makes the transient "just enabled, not
bound yet" window report `permission_required` instead of a confusing
`false`.

## Verification status

- **IMPLEMENTED**: service lifetime, notification, all three stop paths,
  runtime capability checks, `stop_bridge` protocol action — all covered
  by 121 passing SDK tests (including the simulator's teardown behavior).
- **ANDROID-MECHANISM-TESTED**: none of the Android-specific behavior
  (foreground service survival, notification action, projection callback)
  has been exercised on a real device in this sandbox; the manual
  on-device procedure in [`testing.md`](testing.md) covers it.
- **MINI-MILITIA-REAL-DEVICE-VALIDATED**: nothing yet; see
  [`device-validation.md`](device-validation.md).
