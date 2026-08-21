package com.milipy.bridge

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import io.ktor.server.application.install
import io.ktor.server.cio.CIO
import io.ktor.server.engine.embeddedServer
import io.ktor.server.routing.routing
import io.ktor.server.websocket.WebSockets
import io.ktor.server.websocket.webSocket
import io.ktor.websocket.Frame
import io.ktor.websocket.WebSocketSession
import io.ktor.websocket.close
import io.ktor.websocket.readText
import io.ktor.websocket.readBytes
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject

/**
 * The MiliPy Android Bridge service.
 *
 * Responsibilities (per the architecture brief): Android lifecycle, screen
 * capture, input abstraction, game-screen observation, the MiliPy WebSocket
 * server, protocol handling, pairing/authentication, capability reporting,
 * and logging. It does NOT speak Mini Militia's game protocol.
 *
 * Bound to all local interfaces on the configured port (default 8765). The
 * hotspot gateway is discovered at runtime — never hard-coded to 192.168.43.x.
 */
class MiliPyService : Service() {

    private val world = WorldState()
    private val dispatcher = ActionDispatcher(world)

    /** Thread-safe outbound message queue flushed by the observation loop. */
    private val pendingOutbound = java.util.concurrent.ConcurrentLinkedQueue<String>()
    private var ktorServer: io.ktor.server.engine.ApplicationEngine? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        running = true
        BridgeConfig.init(this)
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, 0) ?: 0
        val data = intent?.getParcelableExtra<Intent>(EXTRA_RESULT_DATA)

        if (resultCode != 0 && data != null) {
            val mediaProjectionManager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as
                android.media.projection.MediaProjectionManager
            val projection = mediaProjectionManager.getMediaProjection(resultCode, data)
            if (projection != null) {
                ScreenCapture.start(projection)
            }
        }

        startForeground(NOTIFICATION_ID, buildNotification())
        startKtor()
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        ScreenCapture.stop()
        ktorServer?.stop(1000, 2000)
        ktorServer = null
        super.onDestroy()
    }

    private fun startKtor() {
        ktorServer?.stop(1000, 2000)
        val port = Protocol.DEFAULT_PORT
        ktorServer = embeddedServer(CIO, port = port) {
            install(WebSockets)
            routing {
                webSocket("/") {
                    handleSession(this)
                }
            }
        }.apply { start(wait = false) }
        Log.i(TAG, "MiliPy bridge listening on port $port")
    }

    /**
     * The entire bridge session lives inside a [WebSocketSession]. All send/
     * receive helpers take that session explicitly, which keeps the service
     * itself free of framework coroutine receivers.
     */
    private suspend fun handleSession(session: WebSocketSession) {
        var authorized = false
        var authenticatedAttempts = 0

        // The client must initiate with a `hello` frame.
        val helloFrame = session.awaitInbound() ?: return
        val hello = parseMessage(helloFrame) ?: run {
            session.sendOutbound(errorEnvelope(Protocol.ERR_MALFORMED, "not valid JSON", null))
            return
        }
        if (hello.optString("type") != Protocol.MSG_HELLO ||
            hello.optInt("protocol", -1) != Protocol.VERSION ||
            hello.optString("client") != Protocol.CLIENT_ID) {
            session.sendOutbound(
                JSONObject().put("type", Protocol.MSG_PROTOCOL_ERROR)
                    .put("reason", "protocol_mismatch").put("supported", listOf(Protocol.VERSION))
                    .toString()
            )
            session.close()
            return
        }

        if (BridgeConfig.pairingToken().isNotEmpty()) {
            session.sendOutbound(
                JSONObject().put("type", Protocol.MSG_AUTH_REQUIRED).put("challenge", "pairing")
                    .toString()
            )
            val authFrame = session.awaitInbound() ?: return
            val auth = parseMessage(authFrame)
            if (auth == null || auth.optString("type") != Protocol.MSG_AUTH ||
                !BridgeConfig.verifyPairingToken(auth.optString("token"))) {
                authenticatedAttempts++
                session.sendOutbound(
                    JSONObject().put("type", Protocol.MSG_AUTH_ERROR).put(
                        "reason",
                        if (authenticatedAttempts > 3) "too_many_attempts" else "invalid_token"
                    ).toString()
                )
                session.close()
                return
            }
        }
        authorized = true

        session.sendOutbound(helloAck())
        emitEvent(session, "capture_started", JSONObject())

        // -- tick observation loop -------------------------------------------
        CoroutineScope(currentCoroutineContext()).launch {
            while (authorized) {
                try {
                    val frameJson = if (world.includeFrames) ScreenCapture.captureFrame() else null
                    val state = world.snapshot(ScreenInfo.width(), ScreenInfo.height(), frameJson)
                    session.sendOutbound(JSONObject(state as Map<*, *>).toString())
                    world.nextTick()
                    while (pendingOutbound.poll() != null) {
                        session.sendOutbound(pendingOutbound.poll() ?: break)
                    }
                } catch (_: Exception) {
                    // Observation errors never break the session.
                }
                delay((1000 / BridgeConfig.frameRateLimit().coerceAtLeast(1)).toLong())
            }
        }

        // -- inbound action loop ---------------------------------------------
        while (authorized) {
            val raw = session.awaitInbound() ?: break
            val message = parseMessage(raw)
            if (message == null) {
                session.sendOutbound(errorEnvelope(Protocol.ERR_MALFORMED, "not valid JSON", null))
                continue
            }
            when (message.optString("type")) {
                Protocol.MSG_ACTION -> handleAction(message)
                Protocol.Actions.PING -> {
                    val pingId = message.optString("id").takeIf { it.isNotEmpty() }
                    if (pingId != null) session.sendOutbound(
                        JSONObject().put("type", Protocol.MSG_ACK)
                            .put("id", pingId).put("action", Protocol.Actions.PING)
                            .put("status", "accepted").toString())
                    else session.sendAck(message.optString("request_id"), Protocol.Actions.PING)
                }
                Protocol.Actions.DISCONNECT -> {
                    val disconnectId = message.optString("id").takeIf { it.isNotEmpty() }
                    if (disconnectId != null) session.sendOutbound(
                        JSONObject().put("type", Protocol.MSG_ACK)
                            .put("id", disconnectId).put("action", Protocol.Actions.DISCONNECT)
                            .put("status", "accepted").toString())
                    else session.sendAck(message.optString("request_id"), Protocol.Actions.DISCONNECT)
                    authorized = false
                }
                else -> session.sendOutbound(errorEnvelope(Protocol.ERR_MALFORMED,
                    "unknown message type '${message.optString("type")}'",
                    message.optString("request_id").takeIf { it.isNotEmpty() },
                    message.optString("id").takeIf { it.isNotEmpty() }))
            }
        }
        session.close()
    }

    private fun handleAction(message: JSONObject) {
        val action = message.optString("action", "")
        if (action.isEmpty()) {
            // Action messages always carry an `action` field; drop malformed
            // ones silently — the tick loop stays the authority on output.
            return
        }
        val payload = JSONObject().apply {
            for (key in message.keys()) {
                if (key != "type" && key != "request_id" && key != "action") {
                    put(key, message.opt(key))
                }
            }
        }
        val error = dispatcher.execute(action, payload)
        val requestId = message.optString("request_id").takeIf { it.isNotEmpty() }
        val actionId = message.optString("id").takeIf { it.isNotEmpty() }
        if (error != null) {
            pendingOutbound.add(errorEnvelope(Protocol.ERR_UNSUPPORTED, error, requestId, actionId))
        } else if (requestId != null || actionId != null) {
            pendingOutbound.add(JSONObject().put("type", Protocol.MSG_ACK)
                .apply {
                    if (requestId != null) put("request_id", requestId)
                    if (actionId != null) put("id", actionId)
                    put("action", action)
                    put("status", "accepted")
                }.toString())
        }
        if (action == Protocol.Actions.GET_SETTINGS) {
            pendingOutbound.add(
                JSONObject().put("type", Protocol.MSG_RESULT)
                    .put("request_id", requestId ?: "")
                    .put("action", action)
                    .put("data", JSONObject(BridgeSettings.lastResult))
                    .toString()
            )
        }
    }

    // -- message helpers -----------------------------------------------------

    private fun helloAck(): String = JSONObject().apply {
        put("type", Protocol.MSG_HELLO_ACK)
        put("protocol", Protocol.VERSION)
        put("bridge_version", Protocol.BRIDGE_VERSION)
        put("bridge_id", "MiliPyBridge")
        put("capabilities", CapabilitiesReport.richAll())
        put("screen", JSONObject().apply {
            put("width", ScreenInfo.width())
            put("height", ScreenInfo.height())
            put("density", ScreenInfo.density().toDouble())
        })
        put("device", JSONObject(CapabilitiesReport.deviceInfo()))
        put("session", JSONObject().apply {
            put("tick", world.tick)
            put("frame_rate_limit", BridgeConfig.frameRateLimit())
        })
    }.toString()

    private fun errorEnvelope(
        code: String,
        message: String,
        requestId: String?,
        actionId: String? = null,
    ): String =
        JSONObject().apply {
            put("type", Protocol.MSG_ERROR)
            put("code", code)
            put("message", message)
            if (requestId != null) put("request_id", requestId)
            if (actionId != null) put("id", actionId)
        }.toString()

    private fun parseMessage(text: String): JSONObject? = try {
        JSONObject(text)
    } catch (_: Exception) {
        null
    }

    // -- notification --------------------------------------------------------

    private fun buildNotification(): android.app.Notification {
        return android.app.Notification.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.notification_title))
            .setContentText(
                getString(R.string.notification_text, BridgeConfig.pairingToken())
            )
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(CHANNEL_ID, "MiliPy Bridge",
                NotificationManager.IMPORTANCE_LOW)
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    companion object {
        const val TAG = "MiliPyBridge"
        const val CHANNEL_ID = "milipy_bridge"
        const val NOTIFICATION_ID = 1
        const val EXTRA_RESULT_CODE = "resultCode"
        const val EXTRA_RESULT_DATA = "resultData"

        @Volatile private var running = false
        fun isRunning(): Boolean = running

        fun start(context: Context) {
            context.startForegroundService(Intent(context, MiliPyService::class.java))
        }
    }
}

// -- WebSocket session helpers -----------------------------------------------

private suspend fun WebSocketSession.sendOutbound(text: String) {
    send(Frame.Text(text))
}

private suspend fun WebSocketSession.sendAck(requestId: String?, action: String) {
    if (requestId.isNullOrEmpty()) return
    sendOutbound(
        JSONObject().put("type", Protocol.MSG_ACK)
            .put("request_id", requestId).put("action", action).put("status", "accepted").toString()
    )
}

private suspend fun emitEvent(session: WebSocketSession, eventName: String, data: JSONObject) {
    session.sendOutbound(
        JSONObject().put("type", Protocol.MSG_EVENT)
            .put("event", eventName).put("data", data).toString()
    )
}

/**
 * Await the next inbound frame and return it as text. Binary frames are
 * decoded as UTF-8; close and other frame types terminate reception with
 * ``null``. Never throws — the caller decides how to handle end of stream.
 */
private suspend fun WebSocketSession.awaitInbound(): String? {
    return try {
        when (val frame = incoming.receive()) {
            is Frame.Text -> frame.readText()
            is Frame.Binary -> String(frame.readBytes(), Charsets.UTF_8)
            is Frame.Close -> null
            else -> null
        }
    } catch (_: Exception) {
        null
    }
}
