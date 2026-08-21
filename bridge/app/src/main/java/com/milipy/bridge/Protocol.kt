package com.milipy.bridge

/**
 * MiliPy Bridge Protocol v1 — shared constants.
 *
 * These values are the Kotlin counterpart of the Python SDK's
 * `protocol_schema.py`. Keep them synchronized: the Python tests and this
 * module both validate against the same message shapes.
 *
 * Networking scope: this protocol is the *MiliPy control channel* only.
 * Mini Militia's LAN lobby networking remains entirely the game's own
 * concern; the bridge never speaks the game's protocol.
 */
object Protocol {
    const val VERSION = 1
    const val CLIENT_ID = "milipy"
    const val CLIENT_VERSION = "0.1.0"
    const val BRIDGE_VERSION = "0.1.0"

    const val DEFAULT_PORT = 8765
    const val PAIRING_TOKEN_LENGTH = 6

    // Inbound (client -> bridge)
    const val MSG_HELLO = "hello"
    const val MSG_AUTH = "auth"
    const val MSG_ACTION = "action"

    // Outbound (bridge -> client)
    const val MSG_HELLO_ACK = "hello_ack"
    const val MSG_AUTH_REQUIRED = "auth_required"
    const val MSG_AUTH_ERROR = "auth_error"
    const val MSG_ACK = "ack"
    const val MSG_RESULT = "result"
    const val MSG_EVENT = "event"
    const val MSG_STATE = "state"
    const val MSG_ERROR = "error"
    const val MSG_PROTOCOL_ERROR = "protocol_error"

    // Action names
    object Actions {
        const val MOVE = "move"
        const val STOP = "stop"
        const val JUMP = "jump"
        const val CROUCH = "crouch"
        const val SET_CONTROL = "set_control"
        const val AIM = "aim"
        const val AIM_AT = "aim_at"
        const val FIRE = "fire"
        const val STOP_FIRE = "stop_fire"
        const val PUNCH = "punch"
        const val THROW_GRENADE = "throw_grenade"
        const val PICKUP = "pickup"
        const val SWITCH_WEAPON = "switch_weapon"
        const val CHAT_SEND = "chat_send"
        const val GET_SETTINGS = "get_settings"
        const val SET_SETTING = "set_setting"
        const val SET_CAPTURE = "set_capture"
        const val REQUEST_STATE = "request_state"
        const val PING = "ping"
        const val DISCONNECT = "disconnect"
    }

    val VALID_DIRECTIONS = setOf("left", "right", "up", "down")

    /** Capability -> supported actions in v0.1. */
    val ACTION_CAPABILITIES: Map<String, String?> = mapOf(
        Actions.MOVE to "gesture_input",
        Actions.STOP to "gesture_input",
        Actions.JUMP to "gesture_input",
        Actions.CROUCH to "gesture_input",
        Actions.SET_CONTROL to "gesture_input",
        Actions.AIM to "gesture_input",
        Actions.AIM_AT to "gesture_input",
        Actions.FIRE to "gesture_input",
        Actions.STOP_FIRE to "gesture_input",
        Actions.PUNCH to "gesture_input",
        Actions.THROW_GRENADE to "grenades",
        Actions.PICKUP to "weapons",
        Actions.SWITCH_WEAPON to "weapons",
        Actions.CHAT_SEND to "chat",
        Actions.GET_SETTINGS to "settings_read",
        Actions.SET_SETTING to "settings_write",
        Actions.SET_CAPTURE to null,
        Actions.REQUEST_STATE to null,
        Actions.PING to null,
        Actions.DISCONNECT to null,
    )

    const val ERR_MALFORMED = "malformed_message"
    const val ERR_UNSUPPORTED = "unsupported_capability"
    const val ERR_AUTH = "auth_error"
    const val ERR_PROTOCOL = "protocol_mismatch"
}

/** The game-session observation vocabulary (protocol §8). */
enum class GameSessionState(val value: String) {
    NONE("none"),
    UNKNOWN("unknown"),
    MAIN_MENU("main_menu"),
    LAN_MENU("lan_menu"),
    LOBBY_VISIBLE("lobby_visible"),
    IN_LOBBY("in_lobby"),
    IN_GAME("in_game"),
    GAME_OVER("game_over");

    companion object {
        fun fromString(raw: String): GameSessionState =
            entries.firstOrNull { it.value == raw } ?: UNKNOWN
    }
}
