# MiliPy Bridge Protocol Specification

**Version:** 1
**Document status:** Stable for v0.1
**Transport:** WebSocket (JSON text frames) over local Wi-Fi
**Authors:** MiliPy contributors

## 1. Overview

The MiliPy Bridge Protocol governs all communication between the Python MiliPy SDK (the *client*) and the Kotlin MiliPy Android Bridge (the *server*). Communication is bidirectional, event-driven, and strictly local: the bridge binds to a hotspot interface, and the client connects over the local network. No cloud services, external APIs, or Internet connectivity are involved.

### 1.1 Two networking layers — what this protocol is and is not

MiliPy deliberately separates two completely different networking concepts, and this protocol covers **only the second one**:

| Layer | Owner | Scope |
|-------|-------|-------|
| Mini Militia LAN networking | The Mini Militia game itself | Hotspot creation, LAN lobby discovery, matchmaking, game rules, match lifecycle |
| MiliPy control networking | MiliPy (this protocol) | WebSocket link between the Python SDK and the Kotlin Android bridge |

The bridge observes and controls a *normal, unmodified* Mini Militia Android client through legitimate Android mechanisms (screen capture and accessibility/input dispatch). MiliPy does **not** implement, replace, or reverse-engineer Mini Militia's LAN game protocol. The `host` address used by the SDK refers to the **MiliPy Android Bridge**, never to a Mini Militia game server. LAN lobbies may eventually be *observed* through the visible UI (e.g. `bot.lan_lobbies`), but never queried from game-internal state.

### 1.2 Deployment topologies

The MiliPy-controlled device may be either the Mini Militia LAN host or a client that joins the host's lobby; the SDK must not assume either:

**Topology A — bridge on the host phone:**

```
Host Phone                Termux / bot machine
├── Wi-Fi hotspot         └── MiliPy SDK
├── Mini Militia (host)
└── MiliPy Bridge ──► (connects over the hotspot)
```

**Topology B — bridge on a client phone:**

```
Host Phone                Client Phone          Termux / bot machine
├── Wi-Fi hotspot         ├── MiliPy Bridge     └── MiliPy SDK
└── Mini Militia (host)   └── Mini Militia (client)
```

The end-to-end vertical slice is: hotspot on → Mini Militia running and in a LAN lobby (handled by the game) → bridge running → SDK connected to the bridge → screen observation received → supported action dispatched → result visible on the device.

All messages are UTF-8 encoded JSON objects with a mandatory top-level `type` field. Unknown message types and unknown fields MUST be ignored gracefully by both sides. A `request_id` MAY be included on request/response pairs; if omitted, the response is fire-and-forget.

### Coordinate system

Screen coordinates in this protocol are expressed in one of two forms:

| Form | Field | Range | Origin |
|------|-------|-------|--------|
| Normalized | `nx`, `ny` | `0.0 .. 1.0` | Top-left; x increases right, y increases down |
| Absolute | `x`, `y` | `0 .. screen_width`, `0 .. screen_height` pixels | Same |

Normalized coordinates are preferred for actions (`aim`, `tap`, `hold`) because they are resolution-independent. Absolute coordinates are used for bridge-reported frame dimensions and for the simulator's synthetic state, which models a 1280x720 reference surface.

### Naming

- **Capability:** a boolean feature flag reported by the bridge during handshake. A capability reported as `false` means an action targeting that feature must fail with `UnsupportedCapabilityError` on the SDK side.
- **Tick:** a monotonic server-side observation counter, starting at `1` after the handshake completes.
- **Pairing code:** a 6-character alphanumeric token displayed by the bridge and supplied by the client before the session is authorized.

## 2. Handshake

### 2.1 `hello` (client → bridge)

The first message sent by the client after the WebSocket connection opens.

```json
{
  "type": "hello",
  "protocol": 1,
  "client": "milipy",
  "version": "0.1.0"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | Always `"hello"` |
| `protocol` | integer | yes | Protocol version requested (`1`) |
| `client` | string | yes | Always `"milipy"` |
| `version` | string | yes | SDK version, semver |

### 2.2 `auth_required` (bridge → client)

If the bridge is configured with a pairing requirement (the default), it responds with:

```json
{
  "type": "auth_required",
  "challenge": "pairing"
}
```

### 2.3 `auth` (client → bridge)

```json
{
  "type": "auth",
  "token": "A3X9K2"
}
```

The bridge compares the token against its expected pairing code (constant-time comparison). On success it replies with `hello_ack`; on failure it replies with `auth_error` and closes the connection.

### 2.4 `auth_error` (bridge → client)

```json
{
  "type": "auth_error",
  "reason": "invalid_token"
}
```

Reasons: `"invalid_token"`, `"too_many_attempts"`, `"protocol_mismatch"`.

### 2.5 `hello_ack` (bridge → client)

Sent when the handshake completes (either directly, if pairing is disabled, or after successful `auth`).

```json
{
  "type": "hello_ack",
  "protocol": 1,
  "bridge_version": "0.1.0",
  "bridge_id": "MiliPyBridge",
  "capabilities": {
    "screen_capture": true,
    "gesture_input": true,
    "player_tracking": false,
    "chat": false,
    "settings_read": false,
    "settings_write": false
  },
  "screen": {
    "width": 1280,
    "height": 720,
    "density": 2.0
  },
  "device": {
    "model": "Pixel 6",
    "os_version": "13",
    "bridge": "0.1.0",
    "game_detected": true
  },
  "session": {
    "tick": 0,
    "frame_rate_limit": 10
  }
}
```

| Field | Description |
|-------|-------------|
| `protocol` | Negotiated protocol version. If the bridge cannot support the requested version it replies `protocol_error` instead. |
| `capabilities` | Feature flags. The authoritative list of what this bridge build can actually do. |
| `screen` | The capture surface dimensions in pixels. |
| `session.tick` | Initial tick value. |
| `session.frame_rate_limit` | Maximum observation frames the bridge will push per second. |
| `device` | Android device information and game detection status reported by the bridge (informational; fields may be `null` when unavailable). |

### 2.6 `protocol_error` (bridge → client)

```json
{
  "type": "protocol_error",
  "reason": "unsupported_version",
  "supported": [1]
}
```

## 3. Server-initiated messages

### 3.1 `state` (observation)

The primary periodic observation. The bridge pushes these at up to `frame_rate_limit` per second while capture is running, or in response to a `request_state` action.

```json
{
  "type": "state",
  "tick": 123,
  "timestamp_ms": 1700000000000,
  "frame": {
    "format": "jpeg",
    "encoding": "base64",
    "width": 1280,
    "height": 720,
    "data": "/9j/4AAQ..."
  },
  "player": {
    "id": "self",
    "name": null,
    "position": { "nx": 0.5, "ny": 0.75 },
    "health": 100,
    "max_health": 100,
    "alive": true,
    "weapon": null
  },
  "meta": {
    "source": "screen_capture",
    "confidence": null
  },
  "game_session": "in_game"
}
```

`frame` is omitted when `capabilities.screen_capture` is `false` or when the client disabled frames via `set_capture` (see §4.2). Fields whose value cannot be observed are `null`, never invented.

`game_session` is the bridge's best legitimate observation of the game's high-level session state. Until the perception layer supports fine-grained detection, the bridge MUST report `"unknown"`; once detection is implemented it reports one of: `"none"` (Mini Militia not running), `"main_menu"`, `"lan_menu"`, `"lobby_visible"`, `"in_lobby"`, `"in_game"`, `"game_over"`. The SDK treats any unrecognized value as unknown.

### 3.2 `event`

Discrete occurrences detected by the bridge.

```json
{
  "type": "event",
  "event": "player_seen",
  "tick": 124,
  "data": {
    "player": {
      "id": "p1",
      "name": "Unknown",
      "position": { "nx": 0.3, "ny": 0.4 },
      "health": null
    }
  }
}
```

Defined event names for v0.1:

| Event | Data | Meaning |
|-------|------|---------|
| `capture_started` | `{}` | MediaProjection capture session began |
| `capture_stopped` | `{}` | Capture session ended (user revoked, system stopped) |
| `player_seen` | `{player}` | A player entity was detected in the frame |
| `player_lost` | `{player}` | A tracked player is no longer detected |
| `frame` | `{format, encoding, width, height, data}` | Raw frame without state envelope (throttled) |

Events may carry a `data` object whose shape depends on `event`. Unknown fields inside `data` are ignored.

### 3.3 `error`

Asynchronous errors that are not tied to a request.

```json
{
  "type": "error",
  "code": "capture_unavailable",
  "message": "MediaProjection session stopped by the user."
}
```

### 3.4 `ack` / `result`

Responses to actions that include a `request_id`:

```json
{
  "type": "ack",
  "request_id": "req-7",
  "action": "move"
}
```

```json
{
  "type": "result",
  "request_id": "req-8",
  "action": "get_capabilities",
  "data": { "capabilities": { ... } }
}
```

If an action targets a capability the bridge does not support, the bridge replies:

```json
{
  "type": "error",
  "code": "unsupported_capability",
  "request_id": "req-9",
  "message": "Action 'throw_grenade' requires capability 'grenades' which is not available."
}
```

## 4. Client-initiated messages

All client messages have the envelope:

```json
{
  "type": "action",
  "request_id": "req-1",
  "action": "<name>",
  ...payload fields...
}
```

`request_id` is an opaque string generated by the SDK. If present, the bridge replies with `ack`, `result`, or `error` carrying the same `request_id`.

### 4.1 Movement and control

```json
{"type": "action", "action": "move", "direction": "left"}
```

`direction`: one of `"left"`, `"right"`, `"up"`, `"down"`. Movement actions are *holds*: the gesture/controller sustains the direction until `stop`, `move` with a new direction, or `set_control` changes state.

```json
{"type": "action", "action": "stop"}
```

```json
{
  "type": "action",
  "action": "set_control",
  "left": false,
  "right": true,
  "jump": false,
  "jetpack": false
}
```

`set_control` is the lowest-level control action: each boolean field represents a sustained press state. Only fields present in the payload are changed; omitted fields are untouched.

```json
{"type": "action", "action": "jump"}
```

A tap-action (momentary press). Same family: `crouch`.

### 4.2 Capture control

```json
{
  "type": "action",
  "action": "set_capture",
  "enabled": true,
  "frame_rate": 5,
  "include_frame": true
}
```

Toggles the capture pipeline. `include_frame: false` stops pushing image data while keeping state metadata flowing.

```json
{"type": "action", "action": "request_state"}
```

Immediately triggers a `state` observation.

### 4.3 Aiming

```json
{
  "type": "action",
  "action": "aim",
  "nx": 0.75,
  "ny": 0.42
}
```

A sustained aim: the bridge moves and holds the joystick/aim input toward the given normalized screen point until replaced by another `aim` or `stop`.

```json
{
  "type": "action",
  "action": "aim_at",
  "target": { "nx": 0.6, "ny": 0.5 }
}
```

Alias accepted for symmetry with the SDK's `aim_at(player)` call; functionally identical to `aim`.

### 4.4 Combat

```json
{"type": "action", "action": "fire"}
```

Sustained fire until `stop_fire`.

```json
{"type": "action", "action": "stop_fire"}
```

```json
{"type": "action", "action": "punch"}
```

Momentary tap on the melee button. Not supported until `capabilities` includes it; otherwise the bridge returns `unsupported_capability`.

```json
{"type": "action", "action": "throw_grenade"}
```

Same unsupported-capability handling.

### 4.5 Weapons

```json
{"type": "action", "action": "switch_weapon", "index": 1}
```

```json
{"type": "action", "action": "pickup"}
```

Both return `unsupported_capability` in v0.1.

### 4.6 Chat

```json
{
  "type": "action",
  "action": "chat_send",
  "text": "gg"
}
```

`unsupported_capability` in v0.1.

### 4.7 Settings

```json
{
  "type": "action",
  "action": "get_settings"
}
```

```json
{
  "type": "action",
  "action": "set_setting",
  "key": "bridge.log_level",
  "value": "debug"
}
```

Only MiliPy bridge settings are writable in v0.1 (e.g., `bridge.log_level`, `bridge.frame_rate_limit`). Game settings are read-only observables and are not yet observed.

### 4.8 Session

```json
{"type": "action", "action": "ping"}
```

Replied with `{"type": "ack", "request_id": "...", "action": "ping"}`.

```json
{"type": "action", "action": "disconnect", "reason": "shutdown"}
```

Graceful session teardown; the bridge replies with `ack` and closes the WebSocket normally.

## 5. Malformed message handling

Messages that are not valid UTF-8 JSON, lack a `type` field, or have an unrecognized `type` trigger a single `error` message (`code: "malformed_message"`) and are otherwise ignored. A stream of malformed messages may be throttled to avoid flooding; after repeated violations the bridge MAY close the connection. A malformed message never crashes either side.

## 6. Security

The bridge binds by default to the local interface and requires a pairing code before session authorization. Pairing uses a shared random 6-character alphanumeric token displayed on the bridge UI and entered by the client (`MILIPY_PAIRING` env var or CLI flag). Tokens are compared in constant time; failed attempts are logged and limited. The session is scoped to the local network; the bridge never exposes itself to a public interface by default.

## 7. Versioning rules

Protocol version `1` covers all message types defined here. Adding a message type, adding optional fields, or widening an enum value is a *backwards-compatible* change that does not bump the major protocol version. Removing a type, changing required field semantics, or renaming fields requires a new major version, announced through `protocol_error` with the `supported` list.

## 8. Game session observation (v0.1, honest baseline)

The bridge reports a single `game_session` string in every `state` message. The honest v0.1 baseline is `"unknown"`: the bridge does not pretend to detect screen states it cannot. Roadmap (v0.2+) perception work may narrow this to the enum defined in §3.1. A future `game_session_changed` event will be added when detection becomes reliable enough to emit discrete transitions.

## 9. Design rationale

WebSocket was chosen over raw TCP sockets or HTTP polling because actions (Python → Android) and observations (Android → Python) both need low-latency, persistent, bidirectional transport over local Wi-Fi, and both ecosystems ship mature WebSocket implementations (`websockets` for Python, Ktor for Kotlin). JSON was chosen over a binary format for v0.1 to keep debugging trivial on Termux; a compact binary variant can be negotiated in a future protocol version without changing the transport.
