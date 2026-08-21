# Real-Device Validation Matrix

> **Implemented is not proven.** Every capability below has three distinct levels, and MiliPy never claims a higher level than the evidence supports.

| Level | Meaning |
|---|---|
| **IMPLEMENTED** | The code path exists and is unit/integration tested against the simulator. The Android API call compiles and executes in the bridge. |
| **ANDROID-MECHANISM-TESTED** | The Android API was exercised on a real device and confirmed to do what the API documentation says (e.g., `dispatchGesture` actually dispatched a gesture; MediaProjection actually produced frames). **Mini Militia behavior was NOT verified at this level.** |
| **MINI-MILITIA-REAL-DEVICE-VALIDATED** | The capability was exercised while Mini Militia was running on the device, and the game demonstrably responded (character moved, aim moved, fire registered, etc.). Requires a real phone + Mini Militia + the manual procedure below. |

## Current matrix

No physical Android device is available in the development environment, so the third column is deliberately **empty**. Nothing in this repository currently claims real-device validation. Cells marked `—` are not yet instrumented for mechanism testing.

| Capability | Implemented | Android-mechanism tested | Mini Militia real-device validated | Device | Android version |
|---|---|---|---|---|---|
| Screen capture (MediaProjection) | Yes — bridge builds, `VirtualDisplay` → `ImageReader` → base64 JPEG pipeline is implemented and unit-tested (frame encoding, backpressure) | — | | | |
| Move left | Yes — `dispatchGesture` joystick hold on the left control | — | | | |
| Move right | Yes — same path, mirrored | — | | | |
| Jump | Yes — tap action on the jump zone | — | | | |
| Crouch | Yes — tap action on the crouch zone | — | | | |
| Punch | Yes — tap action on the punch zone | — | | | |
| Aim | Yes — swipe to normalized point, `screen_to_input` transformation | — | | | |
| Fire | Yes — touch hold on fire zone | — | | | |
| Stop fire / stop movement | Yes — gesture cancellation | — | | | |
| Player detection (perception) | Interface only — `BaselineDetector` deliberately sees nothing | — | | | |
| Player tracking | Interface only — `BaselineTracker` holds nobody | — | | | |
| Game session state | Honest `UNKNOWN` baseline only | — | | | |
| Foreground service persistence (v0.3.0) | Yes — foreground service owns the WebSocket listener; `START_STICKY`; persistence and teardown covered by 121 simulator-tested lifecycle tests | — | | | |
| Notification **Stop Bridge** action (v0.3.0) | Yes — persistent notification with stop action, pairing-token-gated `stop_bridge` protocol action, same teardown path | — | | | |
| Runtime capability detection (v0.3.0) | Yes — `gesture_input` = settings-enabled **and** bound; `screen_capture` = live MediaProjection session; revoked capture reported via `capture_stopped` | — | | | |

When a real device becomes available, fill one row at a time, left to right. A row only advances to a column when the corresponding evidence has been recorded (device model, Android version, and date at minimum).

## Manual validation procedure (when a device is available)

Run each test with the bridge app installed, Mini Militia running, and a bot script connected over the local LAN. Record the device model and Android version for every row.

1. **Screen capture.** Enable capture from the bot (`bot.set_capture(enabled=True)`). Confirm the first `frame` event arrives with `format: jpeg` and decodes into a 1280x720 (or device) image. Screenshot the bot's received image alongside the phone's screen; they must match visually.
2. **Movement.** Run `bot.move("right")` for 2 seconds in the Mini Militia lobby or match, then `bot.stop()`. The character must visibly move right, in the intended direction regardless of device orientation, and stop on release. Repeat for `left`.
3. **Jump / crouch / punch.** Execute each once in-game; the character must jump, crouch, or punch respectively. Crouch must persist until a new control state replaces it.
4. **Aim.** `bot.aim(0.5, 0.5)` should center the crosshair. `bot.aim_at(enemy)` must aim at the enemy's observed position. Test in both portrait-locked and landscape-locked orientations.
5. **Fire / stop fire.** Hold fire for one second, then `stop_fire()`. Bullets must flow only during the hold and stop immediately after.
6. **Backpressure.** Flood actions faster than the bridge can apply them and confirm the bridge never stalls, never crashes, and the *latest* action state wins (documented in the protocol spec).
7. **Malformed inputs.** Send garbage frames and unknown actions at the bridge; it must respond with structured `protocol_error` / `malformed_message` errors and stay connected.
8. **Service persistence (v0.3.0).** Start the bridge, connect a bot, then close the app UI completely. The bot must keep receiving state frames and its actions must still apply. Press the **Stop Bridge** notification action and confirm the connection closes, the notification disappears, and the UI shows STOPPED — nothing may falsely report running afterward.
9. **Runtime capability detection (v0.3.0).** Before enabling the accessibility service, `gesture_input` must be `permission_required`, not `unavailable` and never `available`. After enabling it, the report must become `available` once the service binds. Revoke the MediaProjection session mid-session and confirm `capture_stopped` arrives and `screen_capture` is no longer `available`.
10. **Remote shutdown (v0.3.0).** `await bot.stop_bridge_async()` must close the connection from the bridge side, stop the service, and leave the notification gone.

## Provenance rule

Every number a bot consumes must trace to one of: the bridge's observed state, the perception pipeline's detections, or the simulator's deterministic world. The SDK's `Player` fields are `None` when unobserved; the `BaselineDetector` returns no detections rather than guessing; and `GameSession.UNKNOWN` is the default until a validated detector exists. No component may silently fill in fake data.
