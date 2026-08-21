# MiliPy Engineering Audit Report

**Repository:** [bleetcoding/MiliPy](https://github.com/bleetcoding/MiliPy) (public)
**Latest commit:** `a1926dece24aea5be9abd434d9c8f0f2cb389865`
**Versions:** SDK `0.2.0`, protocol spec `1.1`, bridge `0.1.0` (release build)

This report documents the second engineering audit round: the debug APK publication, the implementation of all requested architectural extensions, and an honest accounting of what was actually tested versus what remains unverified. Nothing is presented as working that was not built and exercised in the terminal.

## 1. APK availability

The debug APK was never stored in the repository — build artifacts are deliberately gitignored, which is standard practice. It is now published as a downloadable GitHub Release asset and verified retrievable:

> **[app-debug.apk](https://github.com/bleetcoding/MiliPy/releases/download/v0.1.0/app-debug.apk)** (4.6 MB, HTTP 200 verified)

The asset was rebuilt after the audit changes and re-uploaded to the existing v0.1.0 release, so the download URL now carries the latest bridge code.

## 2. What was implemented in this audit round

### 2.1 Protocol v1.1 extensions (SDK and Kotlin bridge)

The wire protocol gained **action ids**: every outbound action now carries `id: "action-N"`, and the bridge echoes that id on the matching `ack` (with `status: accepted`) or on the `error` envelope for rejections. The SDK exposes `action_ack` and `action_rejected` events, and `ack` replies include a structured `status` field distinguishing accepted from rejected outcomes rather than a silent boolean. On the bridge side, `MiliPyService.kt` echoes ids for actions, ping, disconnect, and unknown-type errors, and `CapabilitiesReport.kt` now reports capabilities as rich status objects (`{"state": "available"|"unavailable", "validated_on_device": false}`) while keeping plain booleans valid per the protocol.

### 2.2 Coordinate calibration (`milipy.coords`)

A new calibration module performs explicit, documented transformations across all relevant spaces: raw pixels, normalized `[0,1]` game coordinates, and Android input event coordinates, including rotation mapping for portrait/landscape differences and per-resolution aspect-ratio handling. It is validated only for the mapping mathematics — viewport-offset behavior against a *real* Mini Militia game screen is not yet tested (see §3).

### 2.3 Perception architecture interfaces (`milipy.perception`)

`FrameSource`, `PerceptionProvider`, `GameStateProvider`, `PlayerDetector`, and `PlayerTracker` are now **real abstract base classes**, not comments. The default baseline deliberately implements them with empty detections — it never fabricates a player it has not genuinely detected. A `SimFrameSource` wires the simulator through the pipeline so the whole SDK can be exercised offline. Perception-based player detection (computer vision on captured frames) remains the v0.2 roadmap item.

### 2.4 Rich capability reporting

`CapabilityStatus` exposes five states — `available`, `unavailable`, `permission_required`, `unsupported`, `not_validated` — at the SDK level, backwards-compatible with the v1 boolean API. The simulator respects the same states in its replies.

### 2.5 Capture tuning and backpressure

`set_capture` now enforces protocol bounds (frame rate `[0, 30]`, JPEG quality `[40, 95]`), and the protocol documents **latest-frame backpressure**: if the bot cannot consume frames as fast as they arrive, stale frames are dropped in favor of the newest, so observation lag never accumulates.

## 3. Documentation added

| Document | Purpose |
|---|---|
| `docs/device-validation.md` | The validation matrix — deliberately empty, plus the manual procedure for filling it in on real devices. |
| `docs/android-compatibility.md` | Platform requirements (minSdk 26 / compileSdk 34), permission model, foreground-service types, and OEM limitations clearly marked unverified. |
| `docs/roadmap.md` | Updated with this round's additions as v0.2 foundations. |
| `README.md` | Version 0.2.0 summary and links to all docs; release link for the APK. |
| `protocol/protocol.md` | §3.4 action ids and ack statuses, §7.1 rich capabilities, §4.9 capture tuning, backpressure semantics. |

## 4. Verified vs. unverified — the honest accounting

**Verified in the terminal during this round:**

| Item | Evidence |
|---|---|
| Python SDK 0.2.0 logic | 116 pytest cases passing (was 84 before this round), incl. 9 perception-interface tests and 4 action-id/ack tests |
| Coordinate calibration | Dedicated tests for rotation round-trips, clamping, resolution and aspect-ratio mapping |
| Kotlin bridge build | `./gradlew assembleDebug` clean build after every audit change; APK size changed (4,546,914 → 4,579,741 bytes) confirming new code compiled in |
| Example bot | `examples/first_bot.py --simulate` spawns and sees sim players |
| Release asset | HTTP GET on the APK URL verified |

**Unverified — requires a real Android device with Mini Militia:**

Everything that touches the physical phone remains **unvalidated** by definition of the honesty policy: MediaProjection consent flow on the user's actual ROM, gesture dispatch accuracy in Mini Militia's coordinate space, calibration constants against a real game screen, frame rates and thermal behavior, OEM-specific behaviors (MIUI/Pixel/Samsung background killing, gesture-service availability), and real-network topology (hotspot host vs. client, firewall rules). `docs/device-validation.md` contains the empty matrix and the exact procedure for filling it in — that is the intended contract between the code as shipped and the code as proven.

## 5. Bottom line

The audit was executed, not performed on paper: 116 tests pass, the bridge compiles, the APK is downloadable, and every gap is documented as a gap. The architecture is unchanged — the bot still talks only to the MiliPy Bridge, and the Bridge still claims nothing it has not demonstrated.
