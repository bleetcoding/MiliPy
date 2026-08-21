"""Protocol serialization, validation, and error types.

This module turns Python objects into protocol-compliant JSON and validates
incoming frames without ever crashing the caller. Invalid frames become
``ProtocolError`` exceptions carrying the rejection reason, so the Bot can
log them and continue.

All message-type strings and capability flags come from
:mod:`milipy.protocol_schema`; nothing is hard-coded here.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .protocol_schema import (
    ACTION_SPECS,
    ALL_CAPABILITIES,
    CLIENT_ID,
    CLIENT_VERSION,
    ERR_MALFORMED_MESSAGE,
    ERR_UNSUPPORTED_CAPABILITY,
    KNOWN_EVENTS,
    PROTOCOL_UNSUPPORTED_VERSION,
    PROTOCOL_VERSION,
)

logger = logging.getLogger("milipy.protocol")


class ProtocolError(Exception):
    """Raised when a message violates the MiliPy Bridge Protocol.

    Attributes:
        code: Stable machine-readable error code (e.g. ``"malformed_message"``).
        message: Human-readable description.
        raw: The original payload that caused the failure, when available.
    """

    def __init__(self, code: str, message: str, raw: Any = None) -> None:
        self.code = code
        self.message = message
        self.raw = raw
        super().__init__(f"[{code}] {message}")


class CapabilityError(ProtocolError):
    """Raised when an action targets a capability the bridge does not report.

    This is the honest failure mode: the action is never silently dropped.
    """

    def __init__(self, action: str, capability: str | None) -> None:
        self.action = action
        self.capability = capability
        if capability is None:
            detail = f"action '{action}' is not defined in protocol {PROTOCOL_VERSION}"
        else:
            detail = f"action '{action}' requires capability '{capability}', which is unavailable"
        super().__init__(ERR_UNSUPPORTED_CAPABILITY, detail)


def parse_message(raw: str | bytes) -> dict[str, Any]:
    """Parse a raw WebSocket frame into a validated message dict.

    Raises ``ProtocolError`` (``code="malformed_message"``) for anything that
    is not a JSON object with a string ``type`` field.
    """
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError(ERR_MALFORMED_MESSAGE, "frame is not valid UTF-8", raw) from exc
    if not isinstance(raw, str):
        raise ProtocolError(ERR_MALFORMED_MESSAGE, "frame is not a text frame", raw)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ProtocolError(ERR_MALFORMED_MESSAGE, "frame is not valid JSON", raw) from exc
    if not isinstance(data, dict):
        raise ProtocolError(ERR_MALFORMED_MESSAGE, "frame is not a JSON object", raw)
    msg_type = data.get("type")
    if not isinstance(msg_type, str):
        raise ProtocolError(ERR_MALFORMED_MESSAGE, "message missing string 'type' field", data)
    data["type"] = msg_type.strip()
    return data


def validate_action_payload(payload: dict[str, Any]) -> None:
    """Validate an action payload against the schema for its action name.

    Raises ``ProtocolError`` for unknown actions, missing required fields,
    wrong enum values, or out-of-range normalized coordinates.
    """
    action = payload.get("action")
    if action not in ACTION_SPECS:
        raise ProtocolError(ERR_MALFORMED_MESSAGE, f"unknown action '{action}'")
    spec = ACTION_SPECS[action]
    for field_name in spec.required:
        if field_name not in payload:
            raise ProtocolError(
                ERR_MALFORMED_MESSAGE,
                f"action '{action}' missing required field '{field_name}'",
            )
    for field_name, allowed in spec.enum_fields.items():
        if field_name in payload and payload[field_name] not in allowed:
            raise ProtocolError(
                ERR_MALFORMED_MESSAGE,
                f"action '{action}' field '{field_name}' must be one of {allowed}",
            )
    for field_name in spec.int_fields:
        if field_name in payload:
            value = payload[field_name]
            if not isinstance(value, int) or isinstance(value, bool):
                raise ProtocolError(
                    ERR_MALFORMED_MESSAGE,
                    f"action '{action}' field '{field_name}' must be an integer",
                )
    for field_name in spec.numeric_fields:
        if field_name in payload:
            value = payload[field_name]
            if not isinstance(value, (int, float)) or not (0.0 <= value <= 1.0):
                raise ProtocolError(
                    ERR_MALFORMED_MESSAGE,
                    f"action '{action}' field '{field_name}' must be a number in [0.0, 1.0]",
                )


def hello_message(version: str = CLIENT_VERSION) -> dict[str, Any]:
    """Build the ``hello`` handshake message."""
    return {
        "type": "hello",
        "protocol": PROTOCOL_VERSION,
        "client": CLIENT_ID,
        "version": version,
    }


def auth_message(token: str) -> dict[str, Any]:
    """Build the ``auth`` message carrying the pairing code."""
    if not isinstance(token, str) or len(token) != 6:
        raise ProtocolError(ERR_MALFORMED_MESSAGE, "pairing token must be a 6-character string")
    return {"type": "auth", "token": token}


def action_message(action: str, request_id: str | None, **kwargs: Any) -> dict[str, Any]:
    """Build a validated ``action`` envelope."""
    payload: dict[str, Any] = {"type": "action", "action": action, **kwargs}
    if request_id is not None:
        payload["request_id"] = request_id
    validate_action_payload(payload)
    return payload


def encode_message(message: dict[str, Any]) -> str:
    """Serialize a protocol message to a JSON text frame."""
    return json.dumps(message, separators=(",", ":"), sort_keys=False)


def decode_frame(raw: str | bytes) -> dict[str, Any] | None:
    """Parse an incoming frame, returning ``None`` on failure.

    Failures are logged as structured warnings rather than raised, so a
    malformed bridge packet never crashes the SDK. Use :func:`parse_message`
    when the caller wants the error as an exception.
    """
    try:
        return parse_message(raw)
    except ProtocolError as exc:
        logger.warning("Dropping malformed frame: %s", exc.message)
        return None


def bridge_capabilities(raw: dict[str, Any]) -> dict[str, bool]:
    """Extract and normalize a capability map from a ``hello_ack`` body.

    Unknown capability keys are preserved but unknown *values* default to
    ``False``; a missing capability is always treated as unavailable.
    """
    caps: dict[str, bool] = {name: False for name in ALL_CAPABILITIES}
    reported = raw.get("capabilities")
    if isinstance(reported, dict):
        for name in ALL_CAPABILITIES:
            value = reported.get(name)
            caps[name] = bool(value) if isinstance(value, (bool, int)) else False
        # Preserve extra capability flags reported by newer bridges.
        for key, value in reported.items():
            if key not in caps and isinstance(value, (bool, int)):
                caps[key] = bool(value)
    return caps


def protocol_version_supported(ack: dict[str, Any]) -> bool:
    """True when the bridge's negotiated protocol version matches ours."""
    return ack.get("protocol") == PROTOCOL_VERSION


def check_event_name(event: str) -> bool:
    """True when an event name is known to protocol version 1."""
    return event in KNOWN_EVENTS
