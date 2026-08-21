package com.milipy.bridge

import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

/**
 * The shared world model behind the MiliPy observation stream.
 *
 * The bridge does not know Mini Militia's internal state; everything here is
 * either client-controlled input state or derived from what the capture and
 * perception layers legitimately observe. Fields that cannot be observed are
 * never invented — observers should read through [snapshot], which returns a
 * plain map matching the protocol `state` message shape.
 */
class WorldState {

    private val tickCounter = AtomicLong(0)

    /** Monotonic observation counter. */
    val tick: Long
        get() = tickCounter.get()

    /** Current sustained movement direction, or null. */
    @Volatile var moveDirection: String? = null

    /** Current sustained aim point in normalized coordinates, or null. */
    @Volatile var aimPoint: Pair<Float, Float>? = null

    /** Whether fire is currently held. */
    @Volatile var firing: Boolean = false

    /** Individual sustained-press flags (lowest-level control state). */
    @Volatile var controlLeft: Boolean = false
    @Volatile var controlRight: Boolean = false
    @Volatile var controlUp: Boolean = false
    @Volatile var controlDown: Boolean = false
    @Volatile var controlJump: Boolean = false
    @Volatile var controlJetpack: Boolean = false

    /** Whether image frames should be included in state observations. */
    @Volatile var includeFrames: Boolean = true

    /**
     * The honest game-session baseline: until the perception layer can
     * actually detect the visible screen, the bridge reports UNKNOWN and
     * nothing else. See Protocol §8.
     */
    val gameSession: GameSessionState = GameSessionState.UNKNOWN

    /** Advance one observation tick and return the new value. */
    fun nextTick(): Long = tickCounter.incrementAndGet()

    /** Snapshot suitable for serialization into a protocol `state` message. */
    fun snapshot(screenWidth: Int, screenHeight: Int, frameJson: Map<String, Any>?): Map<String, Any> {
        val selfPlayer: Map<String, Any?> = mapOf(
            "id" to "self",
            "name" to null,
            "position" to aimPoint?.let { (x, y) -> mapOf("nx" to x, "ny" to y) },
            "health" to null,
            "max_health" to null,
            "alive" to null,
            "weapon" to null,
        )
        val payload = LinkedHashMap<String, Any>()
        payload["type"] = Protocol.MSG_STATE
        payload["tick"] = tick
        payload["timestamp_ms"] = System.currentTimeMillis()
        payload["player"] = selfPlayer
        payload["screen"] = mapOf("width" to screenWidth, "height" to screenHeight)
        payload["game_session"] = gameSession.value
        if (includeFrames && frameJson != null) {
            payload["frame"] = frameJson
        }
        return payload
    }
}
