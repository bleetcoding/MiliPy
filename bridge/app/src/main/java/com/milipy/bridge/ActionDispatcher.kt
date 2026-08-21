package com.milipy.bridge

import org.json.JSONObject

/**
 * Translates MiliPy protocol actions into device input.
 *
 * Action semantics (v0.1):
 *
 * - `move` / `stop` / `set_control` are *holds*: they update the sustained
 *   press state in [WorldState] and are rendered as virtual joystick
 *   positions on screen.
 * - `jump` / `crouch` are momentary taps on their respective button zones.
 * - `aim` is a sustained drag toward the target normalized point.
 * - `fire` / `stop_fire` are holds on the fire button zone.
 *
 * Button zone positions are approximate for a 1280x720 landscape layout and
 * must be calibrated per device/density in a future perception pass. They
 * are never claimed to be pixel-perfect.
 */
class ActionDispatcher(private val world: WorldState) {

    /** Virtual joystick anchor point (absolute pixels) for a 1280x720 surface. */
    private val joystickCenter = Pair(180f, 540f)

    /** Approximate normalized zones for momentary button taps. */
    private val zones = mapOf(
        "jump" to Pair(1130f, 330f),
        "crouch" to Pair(1130f, 500f),
        "fire" to Pair(1150f, 180f),
        "punch" to Pair(1080f, 180f),
    )

    private val service: MiliPyAccessibilityService?
        get() = MiliPyAccessibilityService.current()

    /**
     * Execute an action. Returns a protocol error string when the capability
     * is unavailable, or null on success.
     */
    fun execute(actionName: String, payload: JSONObject): String? {
        val capability = Protocol.ACTION_CAPABILITIES[actionName]
        if (capability != null && !CapabilitiesReport.supports(capability)) {
            return "Action '$actionName' requires capability '$capability' which is not available."
        }

        val svc = service
        when (actionName) {
            Protocol.Actions.MOVE -> {
                val direction = payload.optString("direction", "")
                if (direction !in Protocol.VALID_DIRECTIONS) {
                    return "move requires direction in ${Protocol.VALID_DIRECTIONS}."
                }
                world.moveDirection = direction
                renderJoystick(direction)
                return null
            }
            Protocol.Actions.STOP -> {
                world.moveDirection = null
                svc?.swipe(joystickCenter.first, joystickCenter.second, joystickCenter.first,
                    joystickCenter.second, 0)
                return null
            }
            Protocol.Actions.SET_CONTROL -> {
                payload.optJSONObject("control")?.let { c ->
                    world.controlLeft = c.optBoolean("left", world.controlLeft)
                    world.controlRight = c.optBoolean("right", world.controlRight)
                    world.controlUp = c.optBoolean("up", world.controlUp)
                    world.controlDown = c.optBoolean("down", world.controlDown)
                    world.controlJump = c.optBoolean("jump", world.controlJump)
                    world.controlJetpack = c.optBoolean("jetpack", world.controlJetpack)
                }
                return null
            }
            Protocol.Actions.JUMP -> {
                svc?.tap(zones["jump"]!!.first, zones["jump"]!!.second)
                return null
            }
            Protocol.Actions.CROUCH -> {
                svc?.tap(zones["crouch"]!!.first, zones["crouch"]!!.second)
                return null
            }
            Protocol.Actions.AIM, Protocol.Actions.AIM_AT -> {
                val target = payload.optJSONObject("target")
                val nx = (target?.optDouble("nx") ?: payload.optDouble("nx", -1.0))
                val ny = (target?.optDouble("ny") ?: payload.optDouble("ny", -1.0))
                if (nx !in 0.0..1.0 || ny !in 0.0..1.0) {
                    return "aim requires normalized coordinates nx, ny in [0, 1]."
                }
                val (sx, sy) = normalizedToPixels(nx, ny)
                world.aimPoint = Pair(nx.toFloat(), ny.toFloat())
                svc?.swipe(joystickCenter.first, joystickCenter.second, sx, sy, 120L)
                return null
            }
            Protocol.Actions.FIRE -> {
                world.firing = true
                val (fx, fy) = zones["fire"]!!
                svc?.swipe(fx, fy, fx, fy, 0) // touch-down held by gesture duration
                return null
            }
            Protocol.Actions.STOP_FIRE -> {
                world.firing = false
                return null
            }
            Protocol.Actions.PUNCH -> {
                val (px, py) = zones["punch"]!!
                svc?.tap(px, py, 80L)
                return null
            }
            Protocol.Actions.SET_CAPTURE -> {
                world.includeFrames = payload.optBoolean("enabled", true)
                return null
            }
            Protocol.Actions.REQUEST_STATE -> return null // tick loop emits
            Protocol.Actions.PING -> return null
            Protocol.Actions.DISCONNECT -> return null
            // v0.1 unsupported (gated by capabilities):
            Protocol.Actions.THROW_GRENADE, Protocol.Actions.PICKUP,
            Protocol.Actions.SWITCH_WEAPON, Protocol.Actions.CHAT_SEND ->
                return "Action '$actionName' requires capability '${Protocol.ACTION_CAPABILITIES[actionName]}' which is not available."
            Protocol.Actions.GET_SETTINGS, Protocol.Actions.SET_SETTING ->
                return handleSetting(actionName, payload)
            else -> return "Unknown action '$actionName'."
        }
    }

    private fun renderJoystick(direction: String) {
        val svc = service ?: return
        val (cx, cy) = joystickCenter
        val offset = 110f
        val (dx, dy) = when (direction) {
            "left" -> Pair(cx - offset, cy)
            "right" -> Pair(cx + offset, cy)
            "up" -> Pair(cx, cy - offset)
            "down" -> Pair(cx, cy + offset)
            else -> Pair(cx, cy)
        }
        svc.swipe(cx, cy, dx, dy, 60_000L) // sustained drag
    }

    private fun normalizedToPixels(nx: Double, ny: Double): Pair<Float, Float> {
        val width = ScreenInfo.width()
        val height = ScreenInfo.height()
        return Pair((nx * width).toFloat(), (ny * height).toFloat())
    }

    private fun handleSetting(actionName: String, payload: JSONObject): String? {
        return when (actionName) {
            Protocol.Actions.GET_SETTINGS -> {
                BridgeSettings.lastResult = mapOf(
                    "bridge.frame_rate_limit" to BridgeConfig.frameRateLimit(),
                    "bridge.log_level" to BridgeConfig.logLevel(),
                )
                null
            }
            Protocol.Actions.SET_SETTING -> {
                val key = payload.optString("key", "")
                val value = payload.opt("value") ?: return "set_setting requires a 'value'."
                BridgeSettings.applySetting(key, value)
                null
            }
            else -> "Unknown action '$actionName'."
        }
    }
}
