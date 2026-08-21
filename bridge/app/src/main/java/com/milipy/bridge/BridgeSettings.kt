package com.milipy.bridge

/**
 * In-memory cache of the last `get_settings` result so the tick observer can
 * include it in `result` messages. Only bridge settings are writable in
 * v0.1 (game settings are out of scope — the bridge never touches game
 * internals).
 */
object BridgeSettings {

    @Volatile
    var lastResult: Map<String, Any> = emptyMap()

    fun applySetting(key: String, value: Any) {
        when (key) {
            "bridge.log_level" -> {
                val level = value.toString()
                if (level in setOf("debug", "info", "warn", "error")) {
                    BridgeConfig.setLogLevel(level)
                }
            }
            "bridge.frame_rate_limit" -> {
                val limit = when (value) {
                    is Number -> value.toInt()
                    is String -> value.toIntOrNull() ?: 10
                    else -> 10
                }
                BridgeConfig.setCaptureFrameRateLimit(limit)
            }
        }
    }
}
