# Android Compatibility

This document lists the Android APIs the MiliPy bridge uses, what each one requires on current Android versions, and what has and has not been tested. Compatibility is claimed only for the API level and behavior documented here — not for anything that has not been run on hardware.

## APIs in use

| API | Used for | Minimum API level |
|---|---|---|
| `MediaProjection` | Screen capture consent and `VirtualDisplay` creation | 21 (API 29+ recommended; behavior changed significantly) |
| `VirtualDisplay` | Rendering the captured surface | 21 |
| `ImageReader` | Consuming `VirtualDisplay` frames as JPEG | 19 |
| `AccessibilityService` | `dispatchGesture` for movement/jump/aim/fire | 24 (`dispatchGesture` introduced in API 24) |
| `dispatchGesture` | Synthesizing touches on screen controls | 24 |
| `ForegroundService` (`FOREGROUND_SERVICE_MEDIA_PROJECTION`) | Keeping capture alive while backgrounded | 28 (foreground services); type declared on 29+ |
| Ktor + CIO (`io.ktor:ktor-server-websockets`) | The bridge WebSocket server | — (library, no OS requirement) |

## Minimum supported Android version

The bridge module targets **`minSdk 26`** (see `bridge/app/build.gradle.kts`), which is conservative for `dispatchGesture` (API 24) but reflects the reality that Android 8.0+ is where `MediaProjection` behavior became stable enough for a capture service. The project is built against `compileSdk 34`.

## Permissions

The bridge requests only what each API strictly requires:

| Permission | Purpose | Grant path |
|---|---|---|
| `SYSTEM_ALERT_WINDOW` | Overlay service lifecycle | Manual in Settings |
| `FOREGROUND_SERVICE` / `FOREGROUND_SERVICE_MEDIA_PROJECTION` | Capture service | Manifest-declared |
| `POST_NOTIFICATIONS` (26+) | Service notification | Runtime request |
| `BIND_ACCESSIBILITY_SERVICE` | Gesture service | Manual in Accessibility Settings |
| `INTERNET` | WebSocket server (local only) | Manifest-declared |

MediaProjection itself has **no manifest permission** — it requires the interactive consent dialog (`MediaProjectionManager.createScreenCaptureIntent()`) every time capture starts, and the user can revoke it from the system status bar at any moment. The bridge treats revocation as capture-unavailable and reports it through the capability status.

## Foreground-service requirements

From Android 9 (API 28) a long-running capture service must be a foreground service with a persistent notification, and Android 14 (API 34) requires the new typed `FOREGROUND_SERVICE_MEDIA_PROJECTION` declaration plus `android:foregroundServiceType="mediaProjection"` in the manifest. The bridge declares this. On Android 12+ the notification must also include a data-service type when relevant.

## Lifecycle constraints

The capture session dies when the user revokes consent from the status bar, the device reboots, or the system kills the service (battery optimization on aggressive OEM skins). The accessibility service can be killed when Mini Militia is the foreground app on some OEMs unless it is exempted from battery optimization — the manual validation procedure in `docs/device-validation.md` covers confirming this per device. Gesture injection only works while Mini Militia is in the foreground.

## Known OEM limitations (unverified, for the record)

These are documented community-reported behaviors that have **not** been tested by this project. Treat them as hypotheses until the validation matrix confirms or refutes them on real hardware:

- **Xiaomi/MIUI**: accessibility services are frequently force-killed; requires battery-saver exemption and often "Autostart" permission.
- **Samsung One UI**: gesture dispatch occasionally requires "Draw over other apps" in addition to the accessibility service.
- **Huawei/EMUI**: aggressive background killing can stop the capture service within minutes.
- **Android 13+**: per-app language and notification-permission changes affect the service notification flow.

## What has actually been tested

The bridge **compiles** (AGP 8.7, Kotlin, Ktor) against API 34, and its protocol constants were programmatically verified to match the Python SDK. No capability listed in `docs/device-validation.md` has been mechanism-tested or real-device-validated — this repository does not claim otherwise.
