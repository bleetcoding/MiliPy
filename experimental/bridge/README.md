# MiliPy Android Bridge — Optional Experimental Component

> **This bridge is no longer the core of MiliPy.** The primary project direction
> is a Mineflayer-style standalone Mini Militia LAN client: Python on Termux
> speaks the Mini Militia LAN multiplayer protocol directly, with no phone, no
> screen capture, and no injected automation required. That architecture is
> documented at [`docs/architecture.md`](../../docs/architecture.md), and the
> protocol research status lives in [`protocol/lan-protocol-research.md`](../../protocol/lan-protocol-research.md).

## What this is

The bridge is a Kotlin Android app that automates an *unmodified* Mini Militia
client through legitimate Android mechanisms: `MediaProjection` for screen
capture and the Accessibility Service's `dispatchGesture()` API for input. The
Python SDK talks to it over a versioned local WebSocket protocol (see
[`protocol/protocol.md`](../../protocol/protocol.md)). It was the project's
original architecture before the standalone-LAN-client correction; it is kept
for users who prefer observation-of-a-screen play and as a reference
implementation of the earlier design.

## Status and honesty notes

The app compiles and the SDK's tests (simulator-driven) pass, but no part of
the bridge's interaction with Mini Militia has been validated on a real device:
no on-device UI testing, no real-game interoperability. Capability flags report
runtime state honestly (capture requires a live MediaProjection session;
gesture input requires the accessibility service to be enabled), and
unsupported features raise errors rather than pretending to work. All of this
predates the architecture correction and is unchanged: experimental, unverified
on real hardware.

## Building

```bash
export ANDROID_HOME=$HOME/android-sdk
# (Android SDK + Gradle 8.9 required; see the root README)
gradle assembleDebug
```

The APK lands at `app/build/outputs/apk/debug/app-debug.apk` and is also
attached to the GitHub release. Install on the phone, grant the notification,
media projection, and accessibility permissions through the app's UI, and start
the bridge service. The pairing code shown in the app authenticates the Python
SDK.

## Running the bot against it

The bridge is a separate component with its own protocol; the core Bot's
honest gate refuses raw host strings until the LAN codec is validated, so pass
an explicit adapter when driving the bot through the bridge, or use the SDK's
simulator for offline work. See [`docs/termux.md`](../../docs/termux.md) for
the environment variables and setup.
