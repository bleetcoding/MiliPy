"""Tests for protocol serialization and validation."""

import json

import pytest

from milipy.protocol import (
    CapabilityError,
    ProtocolError,
    action_message,
    auth_message,
    bridge_capabilities,
    decode_frame,
    encode_message,
    hello_message,
    parse_message,
    protocol_version_supported,
)
from milipy.protocol_schema import (
    ACTION_SPECS,
    CLIENT_ID,
    CLIENT_VERSION,
    ERR_MALFORMED_MESSAGE,
    MSG_HELLO,
    MSG_HELLO_ACK,
    PROTOCOL_VERSION,
    VALID_DIRECTIONS,
)


# ---------------------------------------------------------------------------
# Message parsing
# ---------------------------------------------------------------------------


class TestParseMessage:
    def test_valid_json_object(self):
        msg = parse_message('{"type": "state", "tick": 5}')
        assert msg["type"] == "state"
        assert msg["tick"] == 5

    def test_strips_whitespace_type(self):
        msg = parse_message('{"type": "  state  "}')
        assert msg["type"] == "state"

    def test_bytes_input(self):
        msg = parse_message(b'{"type": "ping"}')
        assert msg["type"] == "ping"

    def test_invalid_utf8_raises(self):
        with pytest.raises(ProtocolError) as exc_info:
            parse_message(b"\xff\xfe invalid utf8")
        assert exc_info.value.code == ERR_MALFORMED_MESSAGE

    def test_invalid_json_raises(self):
        with pytest.raises(ProtocolError) as exc_info:
            parse_message("{not json")
        assert exc_info.value.code == ERR_MALFORMED_MESSAGE

    def test_non_object_raises(self):
        with pytest.raises(ProtocolError):
            parse_message("[1, 2, 3]")

    def test_missing_type_raises(self):
        with pytest.raises(ProtocolError):
            parse_message('{"tick": 1}')

    def test_non_string_type_raises(self):
        with pytest.raises(ProtocolError):
            parse_message('{"type": 42}')


# ---------------------------------------------------------------------------
# Decoding (drop-on-failure path)
# ---------------------------------------------------------------------------


class TestDecodeFrame:
    def test_valid_frame(self):
        assert decode_frame('{"type": "tick"}')["type"] == "tick"

    def test_malformed_returns_none(self, caplog):
        assert decode_frame("garbage") is None
        assert "malformed" in caplog.text.lower() or "Malformed" in caplog.text

    def test_never_raises(self):
        # decode_frame must never propagate, even for exotic inputs.
        for raw in (b"\x00", "", "null", "{}", 123):  # type: ignore[arg-type]
            result = decode_frame(raw)  # type: ignore[arg-type]
            assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# Handshake messages
# ---------------------------------------------------------------------------


class TestHelloMessage:
    def test_shape(self):
        msg = hello_message()
        assert msg == {
            "type": MSG_HELLO,
            "protocol": PROTOCOL_VERSION,
            "client": CLIENT_ID,
            "version": CLIENT_VERSION,
        }

    def test_custom_version(self):
        assert hello_message("0.2.0")["version"] == "0.2.0"


class TestAuthMessage:
    def test_valid_token(self):
        assert auth_message("A3X9K2") == {"type": "auth", "token": "A3X9K2"}

    def test_wrong_length(self):
        with pytest.raises(ProtocolError):
            auth_message("TOO-SHORT")


# ---------------------------------------------------------------------------
# Action validation
# ---------------------------------------------------------------------------


class TestActionValidation:
    def test_move_valid(self):
        msg = action_message("move", None, direction="left")
        assert msg["action"] == "move"
        assert msg["direction"] == "left"

    def test_move_bad_direction(self):
        with pytest.raises(ProtocolError):
            action_message("move", None, direction="diagonal")

    def test_move_missing_direction(self):
        with pytest.raises(ProtocolError):
            action_message("move", None)

    def test_aim_normalized_range(self):
        assert action_message("aim", None, nx=0.5, ny=0.5)["nx"] == 0.5
        for bad in (-0.1, 1.1, "0.5"):
            with pytest.raises(ProtocolError):
                action_message("aim", None, nx=bad, ny=0.5)

    def test_unknown_action(self):
        with pytest.raises(ProtocolError):
            action_message("teleport", None)

    def test_request_id_preserved(self):
        msg = action_message("ping", "req-7")
        assert msg["request_id"] == "req-7"

    def test_all_actions_have_specs(self):
        # Every action exposed by ActionBuilder must validate.
        for name in ACTION_SPECS:
            spec = ACTION_SPECS[name]
            msg = action_message(name, None, **{f: v for f in spec.required
                                                for v in (["left"] if f == "direction" else [1] if f == "index" else [0.5] if f in ("nx", "ny") else [""])})
            assert msg["action"] == name

    def test_switch_weapon_requires_int_index(self):
        with pytest.raises(ProtocolError):
            action_message("switch_weapon", None, index="one")


# ---------------------------------------------------------------------------
# Serialization round trip
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_round_trip(self):
        original = hello_message()
        raw = encode_message(original)
        assert json.loads(raw) == original
        assert raw == json.dumps(original, separators=(",", ":"))

    def test_no_extra_whitespace(self):
        assert " " not in encode_message({"type": "ping"})


# ---------------------------------------------------------------------------
# Capability extraction
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_full_report(self):
        caps = bridge_capabilities({
            "capabilities": {"screen_capture": True, "gesture_input": True}
        })
        assert caps["screen_capture"] is True
        assert caps["player_tracking"] is False

    def test_missing_key_defaults_false(self):
        caps = bridge_capabilities({"capabilities": {}})
        assert all(value is False for value in caps.values())

    def test_non_bool_values_default_false(self):
        caps = bridge_capabilities({"capabilities": {"chat": "yes"}})
        assert caps["chat"] is False

    def test_extra_capabilities_preserved(self):
        caps = bridge_capabilities({"capabilities": {"grenades": True}})
        assert caps["grenades"] is True

    def test_no_capabilities_key(self):
        caps = bridge_capabilities({})
        assert all(value is False for value in caps.values())


class TestProtocolVersion:
    def test_matching(self):
        assert protocol_version_supported({"protocol": PROTOCOL_VERSION})

    def test_mismatch(self):
        assert not protocol_version_supported({"protocol": 99})


class TestCapabilityError:
    def test_message_mentions_capability(self):
        error = CapabilityError("throw_grenade", "grenades")
        assert "grenades" in error.message
        assert error.action == "throw_grenade"
