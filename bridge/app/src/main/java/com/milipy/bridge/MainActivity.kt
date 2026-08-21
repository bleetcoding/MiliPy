package com.milipy.bridge

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.TextView
import android.widget.Toast

/**
 * MiliPy Bridge launcher activity.
 *
 * Hosts the UI for the pairing code, starting/stopping the bridge service
 * (which requests MediaProjection consent when screen capture is provided),
 * and jumping to the system accessibility settings so the user can enable
 * the gesture input service themselves — a deliberate consent gate.
 *
 * Lifetime note (v0.3.0): **the activity is not the lifetime owner.** The
 * bridge runs inside the MiliPy foreground service; the user can close this
 * activity, switch apps, or lock the phone and the bridge keeps serving
 * SDK clients. This UI only *reflects* the service's real state — it reads
 * `MiliPyService.isRunning()`, which the service itself maintains, and
 * every stop action (notification button, this Stop button, the
 * `stop_bridge` protocol action) tears down the listener for real.
 *
 * Deliberately does not depend on AppCompat; this keeps the dependency
 * surface minimal. Plain framework Activity is sufficient.
 */
class MainActivity : Activity() {

    private lateinit var statusText: TextView
    private lateinit var pairingText: TextView
    private lateinit var startButton: Button
    private lateinit var stopButton: Button
    private lateinit var accessibilityButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        statusText = findViewById(R.id.status_text)
        pairingText = findViewById(R.id.pairing_text)
        startButton = findViewById(R.id.start_button)
        stopButton = findViewById(R.id.stop_button)
        accessibilityButton = findViewById(R.id.accessibility_button)

        pairingText.text = "Pairing code: ${BridgeConfig.pairingToken()}"

        startButton.setOnClickListener {
            // MediaProjection consent first (honest capture gating):
            // screen_capture only becomes true after the system dialog is
            // accepted and the session reaches the foreground service.
            val projectionManager = getSystemService(
                android.content.Context.MEDIA_PROJECTION_SERVICE
            ) as android.media.projection.MediaProjectionManager
            startActivityForResult(
                projectionManager.createScreenCaptureIntent(),
                CAPTURE_REQUEST
            )
        }

        stopButton.setOnClickListener {
            val intent = Intent(this, MiliPyService::class.java).apply {
                action = MiliPyService.ACTION_STOP
            }
            startService(intent)
            Toast.makeText(this, "Bridge stopped.", Toast.LENGTH_SHORT).show()
            refreshStatus()
        }

        accessibilityButton.setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }

        refreshStatus()
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == CAPTURE_REQUEST && resultCode == Activity.RESULT_OK && data != null) {
            val intent = Intent(this, MiliPyService::class.java).apply {
                putExtra(MiliPyService.EXTRA_RESULT_CODE, resultCode)
                putExtra(MiliPyService.EXTRA_RESULT_DATA, data)
            }
            startForegroundService(intent)
            refreshStatus()
        }
    }

    private fun refreshStatus() {
        val serviceRunning = MiliPyService.isRunning()
        val accessibilityEnabled = MiliPyAccessibilityService.isEnabledInSettings(this)
        val captureAvailable = ScreenCapture.isAvailable()
        startButton.isEnabled = !serviceRunning
        stopButton.isEnabled = serviceRunning
        statusText.text = buildString {
            appendLine("MiliPy Bridge: ${if (serviceRunning) "RUNNING" else "STOPPED"}")
            appendLine("Input gestures: ${if (accessibilityEnabled) "ENABLED" else "disabled — press the button below to enable"}")
            appendLine("Screen capture: ${if (captureAvailable) "ACTIVE" else "inactive — grant capture consent when starting"}")
        }
    }

    companion object {
        private const val CAPTURE_REQUEST = 1001
    }
}
