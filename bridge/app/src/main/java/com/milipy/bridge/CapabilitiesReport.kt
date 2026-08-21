package com.milipy.bridge

/**
 * The authoritative capability flags reported in `hello_ack`.
 *
 * A flag is `true` only when the bridge can *actually* back the feature with
 * a legitimate Android mechanism that is enabled by the user. The honest
 * v0.1 baseline is: screen capture and gesture input behind consent,
 * everything else disabled.
 */
object CapabilitiesReport {

    fun all(): Map<String, Boolean> = mapOf(
        "screen_capture" to ScreenCapture.isAvailable(),
        "gesture_input" to MiliPyAccessibilityService.isAvailable(),
        "player_tracking" to false,
        "chat" to false,
        "settings_read" to true,
        "settings_write" to true,
    )

    fun supports(feature: String): Boolean = all().getOrElse(feature) { false }

    /**
     * Protocol v1.1 extension: capabilities as rich status objects.
     *
     * Each entry is `{"state": "available" | "unavailable", "validated_on_device": false}`.
     * Boolean values remain valid in the protocol; rich objects carry the
     * honest distinction between *mechanism available* and *not yet proven on
     * a real Mini Militia device*. See docs/device-validation.md.
     */
    fun richAll(): Map<String, Map<String, Any>> =
        all().mapValues { (_, available) ->
            mapOf(
                "state" to (if (available) "available" else "unavailable"),
                "validated_on_device" to false,
            )
        }

    /** Device information for the `device` block of `hello_ack`. */
    fun deviceInfo(): Map<String, Any?> {
        return mapOf(
            "model" to android.os.Build.MODEL,
            "os_version" to android.os.Build.VERSION.RELEASE,
            "bridge" to Protocol.BRIDGE_VERSION,
            "game_detected" to null, // no internal game introspection — honest baseline
        )
    }
}
