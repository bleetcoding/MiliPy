# MiliPy Research Notes

## Mini Militia API status
- No official documented game API or bot interface exists (Appsomniacs/Miniclip publish via Play Store/App Store only; no dev docs, no SDK, no modding API).
- Therefore the external bridge architecture (screen observation + input injection via public Android APIs) is the only legitimate path. Confirming brief's section 36: proceed with bridge architecture; no protocol reverse-engineering.

## Screen capture: MediaProjection (android.media.projection)
- Introduced API 21; captures device display as media stream.
- Android 14 (API 34): app screen sharing lets user share a single app window (good for targeting just Mini Militia), excludes status/nav bar.
- Requires: FOREGROUND_SERVICE + FOREGROUND_SERVICE_MEDIA_PROJECTION permission; service with foregroundServiceType="mediaProjection"; startForeground().
- User consent every session via MediaProjectionManager.createScreenCaptureIntent() startActivityForResult.
- Token used once; createVirtualDisplay() throws SecurityException if reused.
- Output via ImageReader/Surface → frames accessible in real time (ImageReader.acquireLatestImage() → Bitmap).
- onCapturedContentResize callback for size changes; onStop callback for session end.
- Android 14+: status bar chip lets user auto-stop; MediaProjection can't capture content from FLAG_SECURE windows.

## Input: AccessibilityService gestures
- AccessibilityService + accessibility_service_config.xml with android:canPerformGestures="true".
- dispatchGesture(GestureDescription, GestureResultCallback, Handler) — taps, swipes, multi-touch via Path strokes.
- Works for non-privileged app input simulation; user must grant Accessibility permission in system settings (explicit consent flow).
- Caveat: some reports of dispatchGesture touch events not firing in certain environments — test carefully.
- performGlobalAction() for back/home etc.

## WebSocket libraries
- Kotlin/Ktor: ktor-server-websockets + ktor-server-cio (works on Android? Ktor CIO has limitations on Android; better: ktor-server-websockets + OKHttp? Actually Ktor supports Android for client; for server on Android use ktor-server-websockets with CIO or OkHttp-based server). Practical choice: Ktor server (CIO engine) for WebSocket server on Android — works on Android.
- Python: websockets library (asyncio, mature) or websocket-client (sync). Asyncio + websockets is the modern choice.

## Termux / hotspot networking
- Phone hotspot default gateway is typically 192.168.43.1 but must not be hard-coded; use ip route / gateway detection, document.
- Termux: pkg install python; pip install milipy / -e .; no internet needed at runtime after install.
- Android hotspot may block client-to-client traffic on some versions; bridge runs on the phone (server), Termux connects as client — this direction works.

## Other facts
- MediaProjection + AccessibilityService both require explicit user consent flows; never silent.
- No root, no hidden APIs per brief.
- Ktor version: 2.3.x stable. Kotlin 1.9.x. AGP 8.x. compileSdk 34, targetSdk 34, minSdk 26.
- Python: 3.10+. pytest, ruff.

## Capability decisions for v0.1
- screen_capture: true (MediaProjection, consent flow)
- input: gesture-based (AccessibilityService gestures) — marked as available with consent; aim/move translated into gesture strokes
- player_tracking: false (v0.2+)
- chat: false (v0.4)
- grenade/punch: unsupported-capability errors (v0.3)
