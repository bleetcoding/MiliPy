package com.milipy.bridge

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Handler
import android.os.Looper

/**
 * The input leg of the MiliPy control channel.
 *
 * Provides the ability to dispatch touch gestures (taps, swipes, sustained
 * holds) on the device display. This requires the user to explicitly enable
 * the accessibility service in system settings — a deliberate consent gate —
 * and `canPerformGestures="true"` in the service configuration.
 *
 * Gestures are expressed in absolute display pixels; the SDK layer converts
 * normalized coordinates (nx, ny) to pixels using the reported screen size.
 */
class MiliPyAccessibilityService : AccessibilityService() {

    private val mainHandler = Handler(Looper.getMainLooper())

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
    }

    override fun onUnbind(intent: android.content.Intent?): Boolean {
        instance = null
        return super.onUnbind(intent)
    }

    override fun onAccessibilityEvent(event: android.view.accessibility.AccessibilityEvent?) {
        // Intentionally unused: we only use gestures, not event interception.
    }

    override fun onInterrupt() {
        // Nothing to clean up.
    }

    /** Dispatch a single tap at the given display coordinates. */
    fun tap(x: Float, y: Float, durationMs: Long = 100L) {
        val path = Path().apply { moveTo(x, y) }
        val stroke = GestureDescription.StrokeDescription(path, 0, durationMs)
        dispatchGesture(GestureDescription.Builder().addStroke(stroke).build(), null, mainHandler)
    }

    /**
     * Dispatch a swipe from one point to another — used for sustained
     * movement holds translated into drag gestures.
     */
    fun swipe(fromX: Float, fromY: Float, toX: Float, toY: Float, durationMs: Long) {
        val path = Path().apply {
            moveTo(fromX, fromY)
            lineTo(toX, toY)
        }
        val stroke = GestureDescription.StrokeDescription(path, 0, durationMs)
        dispatchGesture(GestureDescription.Builder().addStroke(stroke).build(), null, mainHandler)
    }

    companion object {
        @Volatile
        private var instance: MiliPyAccessibilityService? = null

        /** True while the user has enabled the service in system settings. */
        fun isAvailable(): Boolean = instance != null

        fun current(): MiliPyAccessibilityService? = instance
    }
}
