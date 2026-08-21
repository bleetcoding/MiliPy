package com.milipy.bridge

import android.content.Context

/**
 * Bridge-wide configuration: pairing token, frame rate limit, log level.
 *
 * The pairing token is the shared secret displayed in the app UI and
 * supplied by the client (`MILIPY_PAIRING` env var). It is compared in
 * constant time before a session is authorized.
 */
object BridgeConfig {

    private const val PREFS_NAME = "milipy_bridge"
    private const val KEY_PAIRING_TOKEN = "pairing_token"
    private const val KEY_FRAME_RATE_LIMIT = "frame_rate_limit"
    private const val KEY_LOG_LEVEL = "log_level"

    private val context: Context by lazy {
        throw IllegalStateException("BridgeConfig.init(context) must be called first")
    }

    fun init(ctx: Context) {
        // Stored via simple SharedPreferences-backed holder; the app itself
        // does not depend on EncryptedSharedPreferences at build time.
        holder = ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    private var holder: android.content.SharedPreferences? = null

    private fun putString(key: String, value: String) {
        holder?.edit()?.putString(key, value)?.apply()
    }

    private fun putInt(key: String, value: Int) {
        holder?.edit()?.putInt(key, value)?.apply()
    }

    fun pairingToken(): String {
        val prefs = holder ?: return ""
        val stored = prefs.getString(KEY_PAIRING_TOKEN, null)
        if (!stored.isNullOrEmpty()) return stored
        val token = generateToken()
        putString(KEY_PAIRING_TOKEN, token)
        return token
    }

    fun setPairingTokenFromUI(token: String) {
        putString(KEY_PAIRING_TOKEN, token)
    }

    fun frameRateLimit(): Int = holder?.getInt(KEY_FRAME_RATE_LIMIT, 10) ?: 10

    fun setCaptureFrameRateLimit(limit: Int) {
        putInt(KEY_FRAME_RATE_LIMIT, limit.coerceIn(1, 30))
    }

    fun logLevel(): String = holder?.getString(KEY_LOG_LEVEL, "info") ?: "info"

    fun setLogLevel(level: String) {
        putString(KEY_LOG_LEVEL, level)
    }

    private fun generateToken(): String {
        val chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return buildString {
            repeat(Protocol.PAIRING_TOKEN_LENGTH) {
                append(chars.random())
            }
        }
    }

    /** Constant-time comparison to avoid timing side channels. */
    fun verifyPairingToken(provided: String?): Boolean {
        val expected = pairingToken()
        if (expected.isEmpty() || provided.isNullOrBlank()) return false
        if (expected.length != provided.length) return false
        var mismatch = 0
        for (i in expected.indices) {
            mismatch = mismatch or (expected[i].code xor provided[i].code)
        }
        return mismatch == 0
    }
}
