package com.milipy.bridge

import android.content.Context

/**
 * The authoritative capability flags reported in `hello_ack`.
 *
 * A flag is `true` only when the bridge can *actually* back the feature with
 * a legitimate Android mechanism that is **currently running** — not just
 * implemented in code. The detection rules are deliberately pessimistic:
 *
 * - `gesture_input` is true only when the accessibility service is enabled
 *   **in system settings** (`Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES`)
 *   **and** bound to this process (`MiliPyAccessibilityService.isAvailable()`).
 *   An enabled service that has not finished binding, or a bound service the
 *   user just revoked, must not lie.
 * - `screen_capture` is true only while a live `MediaProjection` session is
 *   actively feeding the virtual display. Consent given earlier that was
 *   later revoked reports false.
 * - Everything else is the honest baseline: implemented-but-unvalidated
 *   surfaces stay false; features that need user consent are never reported
 *   as available before the consent actually exists.
 *
 * These checks happen on every `hello_ack` (and can be re-read via
 * `get_settings`), so a capability report is a snapshot of real device
 * state at that moment — never a cached promise from install time.
 */
object CapabilitiesReport {

    @Volatile private var context: Context? = null

    fun configure(context: Context) {
        this.context = context.applicationContext
    }

    private fun appContext(): Context = context ?: throw IllegalStateException(
        "CapabilitiesReport configured after first use"
    )

    /** True when the accessibility consent gate is fully satisfied. */
    private fun gestureInputAvailable(): Boolean {
        val settingsEnabled = MiliPyAccessibilityService.isEnabledInSettings(appContext())
        val boundToProcess = MiliPyAccessibilityService.isAvailable()
        return settingsEnabled && boundToProcess
    }

    fun all(): Map<String, Boolean> = mapOf(
        "screen_capture" to ScreenCapture.isAvailable(),
        "gesture_input" to gestureInputAvailable(),
        "player_tracking" to false,
        "chat" to false,
        "settings_read" to true,
        "settings_write" to true,
        "stop_bridge" to true, // protocol action: pairing-token-gated remote shutdown
    )

    fun supports(feature: String): Boolean = all().getOrElse(feature) { false }

    /**
     * Protocol v1.1 extension: capabilities as rich status objects.
     *
     * Each entry is
     * `{"state": "available" | "unavailable" | "permission_required",
     *   "validated_on_device": false}`.
     *
     * `permission_required` means a legitimate Android mechanism exists but
     * the user has not granted the consent that activates it — the service
     * is not enabled in settings for `gesture_input`, or the MediaProjection
     * session has not been created/has been revoked for `screen_capture`.
     * A bridge that reports `unavailable` has no mechanism at all; a bridge
     * that reports `available` is doing it right now.
     */
    fun richAll(): Map<String, Map<String, Any>> = mapOf(
        "screen_capture" to status(
            ScreenCapture.isAvailable(),
            ScreenCapture.isAvailable()
        ),
        "gesture_input" to status(
            MiliPyAccessibilityService.isAvailable(),
            gestureInputAvailable()
        ),
        "player_tracking" to notImplemented(),
        "chat" to notImplemented(),
        "settings_read" to base("available"),
        "settings_write" to base("available"),
        "stop_bridge" to base("available"),
    )

    private fun status(availableNow: Boolean, fullySatisfied: Boolean): Map<String, Any> =
        when {
            availableNow -> base("available")
            !fullySatisfied -> base("permission_required")
            else -> base("unavailable")
        }

    private fun notImplemented(): Map<String, Any> = base("unavailable")

    private fun base(state: String): Map<String, Any> = mapOf(
        "state" to state,
        "validated_on_device" to false,
    )

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
