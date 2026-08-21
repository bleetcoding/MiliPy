# MiliPy Testing Guide

## Offline testing (no phone required)

The Python SDK ships an in-memory simulator (`SimAdapter`) that implements the full bridge protocol, including capability negotiation, state observation, and action errors. This is how the entire bot API is exercised in CI and on a developer laptop.

```bash
cd sdk
python3 -m pytest          # 84 tests covering protocol, events, state, actions, simulation
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
| 4 | Phone A: install `app-debug.apk` (`adb install bridge/app/build/outputs/apk/debug/app-debug.apk`), open *MiliPy Bridge*, tap **Start bridge** |
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

Input actions require the user to enable the bridge's accessibility service. In the app, tap **Enable input gestures**, which opens the system accessibility settings; switch *MiliPy Bridge* on. Without this, `gesture_input` stays `false` and input actions raise `CapabilityError`.

### Expected observations

On a successful run you should see, in order: the `ready` event, the `hello_ack` with capabilities and device info, recurring `tick` state messages (with optional base64 JPEG frames), `player_seen` events when simulated or visible players appear, and an `ack` for every accepted action. Frame delivery only works after the MediaProjection consent dialog was accepted when starting the bridge.

### Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ConnectionRefusedError` | Bridge not running, or Termux is on a different network than the bridge |
| `auth_error: invalid_token` | Pairing code mismatch — re-copy the code from the bridge notification |
| `protocol_error: protocol_mismatch` | SDK and bridge version mismatch — rebuild the APK against the current repo |
| Actions raise `CapabilityError` | Enable the accessibility service; grant capture consent when starting the bridge |
| No frames in state | Capture was declined or projection was revoked; restart the bridge and accept the system dialog |
| Actions do nothing in-game | Gesture zones are approximate 1280×720 values; button zones need per-device calibration (see `ActionDispatcher.kt`) |
