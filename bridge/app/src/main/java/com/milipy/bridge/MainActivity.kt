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
 * Hosts the UI for the pairing code, starting the bridge service (which
 * requests MediaProjection consent when screen capture is provided), and
 * jumping to the system accessibility settings so the user can enable the
 * gesture input service themselves — a deliberate consent gate.
 *
 * Deliberately does not depend on AppCompat; this keeps the dependency
 * surface minimal. Plain framework Activity is sufficient.
 */
class MainActivity : Activity() {

    private lateinit var statusText: TextView
    private lateinit var pairingText: TextView
    private lateinit var startButton: Button
    private lateinit var accessibilityButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        statusText = findViewById(R.id.status_text)
        pairingText = findViewById(R.id.pairing_text)
        startButton = findViewById(R.id.start_button)
        accessibilityButton = findViewById(R.id.accessibility_button)

        pairingText.text = "Pairing code: ${BridgeConfig.pairingToken()}"

        startButton.setOnClickListener {
            MiliPyService.start(this)
            startButton.isEnabled = false
            Toast.makeText(this, "Bridge started — check the notification for status.",
                Toast.LENGTH_SHORT).show()
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
        val accessibilityEnabled = isAccessibilityEnabled()
        statusText.text = buildString {
            appendLine("MiliPy Bridge: ${if (serviceRunning) "RUNNING" else "STOPPED"}")
            appendLine("Input gestures: ${if (accessibilityEnabled) "ENABLED" else "disabled — press the button below to enable"}")
        }
    }

    private fun isAccessibilityEnabled(): Boolean {
        val enabledServices = Settings.Secure.getString(
            contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ) ?: return false
        val serviceName = "${packageName}/${MiliPyAccessibilityService::class.java.name}"
        return enabledServices.contains(serviceName)
    }

    companion object {
        private const val CAPTURE_REQUEST = 1001
    }
}
