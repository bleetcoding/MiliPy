# MiliPy Testing Guide

## Offline testing (no phone required)

The Python SDK ships an in-memory simulator (`SimAdapter`) that implements the full bridge protocol, including capability negotiation, state observation, and action errors. This is how the entire bot API is exercised in CI and on a developer laptop.

```bash
cd sdk
python3 -m pytest          # 124 tests covering protocol, events, state, actions, calibration, perception, service lifecycle
python3 tests/smoke.py     # live end-to-end demo against the simulator
```

## On-device integration test (vertical slice)

This is the first real integration test, described in [`architecture.md`](architecture.md). Choose a topology first.

### Topology A — bridge on the host phone

| Step | Action |
|---|---|
| 1 | Phone A: enable the Android Wi-Fi hotspot |
| 2 | Phone A: launch Mini Militia and host a LAN game |
| 3 | Phone B (or another device): connect to Phone A's hotspot, launch Mini Militia, join the LAN lobby |
| 4 | Phone A: install `app-debug.apk` (`adb install bridge/app/build/outputs/apk/debug/app-debug.apk`), open *MiliPy Bridge*, tap **Start bridge**, accept the screen-capture system dialog |
| 5 | Note the pairing code shown in the app |
| 6 | Termux on Phone B (or a laptop on the hotspot network): `pip install -e sdk` |
| 7 | Run a bot: `MILIPY_PAIRING=<code> python3 examples/first_bot.py` with `host="192.168.43.1"` (the hotspot gateway) |
| 8 | Observe: the bot prints `ready`, receives screen frames, and its `move("right")` visibly moves the character on Phone A |

### Topology B — bridge on a client phone

| Step | Action |
|---|---|
| 1 | Phone A: enable hotspot and host the Mini Militia LAN game |
| 2 | Phone B: connect to the hotspot, join the LAN lobby as a client |
| 3 | Phone B: install and start the MiliPy Bridge, note its pairing code and LAN IP (`Settings → About phone` or the notification) |
| 4 | Termux on Phone A or a laptop on the network: run a bot pointing at Phone B's IP |
| 5 | Observe the bot's actions applied on Phone B's Mini Militia client |

### Enabling input gestures

Input actions require the user to enable the bridge's accessibility service. In the app, tap **Enable input gestures**, which opens the system accessibility settings; switch *MiliPy Bridge* on. Without this, `gesture_input` reports `permission_required` and input actions raise `CapabilityError`.

### Service persistence (v0.3.0)

The bridge runs in a foreground service, so closing the app must not stop it. Verify with:

| Step | Action |
|---|---|
| 1 | Start the bridge and connect a bot as described above |
| 2 | Close the *MiliPy Bridge* activity (back button or home screen); the bot must keep receiving `tick` messages and its actions must still apply |
| 3 | Check the persistent **"MiliPy Bridge — Running"** notification in the shade; tap **Stop Bridge** — the bot's connection must close |
| 4 | Alternatively, send `stop_bridge` from the bot (`await bot.stop_bridge_async()`); the connection must close and the notification must disappear |
| 5 | Verify the app UI now shows **STOPPED** and the Stop button is disabled |

`session.transport` in `hello_ack` should be `"foreground_service"`.

### Expected observations

On a successful run you should see, in order: the `ready` event, the `hello_ack` with capabilities and device info, recurring `tick` state messages (with optional base64 JPEG frames), `player_seen` events when simulated or visible players appear, and an `ack` for every accepted action. Capability flags reflect live runtime state: `gesture_input` and `screen_capture` report `"available"` only when the accessibility service is enabled-and-bound and the capture session is live respectively; a revoked capture session is reported immediately via the `capture_stopped` event.

### Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ConnectionRefusedError` | Bridge not running, or Termux is on a different network than the bridge |
| `auth_error: invalid_token` | Pairing code mismatch — re-copy the code from the bridge notification |
| `protocol_error: protocol_mismatch` | SDK and bridge version mismatch — rebuild the APK against the current repo |
| Actions raise `CapabilityError` | Enable the accessibility service; grant capture consent when starting the bridge |
| Bot disconnects after closing the app | Outdated APK — the bridge was still activity-owned; update to v0.3.0 (foreground service) |
| Capability report shows `permission_required` after enabling gestures | The service has not bound yet — wait a moment or reconnect the bot |
| No frames in state | Capture was declined or projection was revoked; restart the bridge and accept the system dialog |
| Actions do nothing in-game | Gesture zones are approximate 1280×720 values; button zones need per-device calibration (see `ActionDispatcher.kt`) |
