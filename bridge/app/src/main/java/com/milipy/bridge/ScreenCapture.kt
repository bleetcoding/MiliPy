package com.milipy.bridge

import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import java.io.ByteArrayOutputStream
import java.util.concurrent.atomic.AtomicReference

/**
 * Screen capture leg of the MiliPy observation stream.
 *
 * Uses a `MediaProjection` virtual display (user consented via
 * `MediaProjectionManager.createScreenCaptureIntent()`) feeding an
 * `ImageReader`. Frames are grabbed on demand by the observation tick loop.
 *
 * Android 14+ lets the user share a single app window (Mini Militia only),
 * which is the ideal configuration. Capture cannot read content from
 * `FLAG_SECURE` windows — by design.
 */
object ScreenCapture {

    @Volatile
    private var virtualDisplay: VirtualDisplay? = null

    private val imageReader = AtomicReference<ImageReader?>(null)

    private var capturedWidth = 0
    private var capturedHeight = 0

    fun isAvailable(): Boolean = virtualDisplay != null

    fun start(mediaProjection: MediaProjection) {
        stop()
        val width = ScreenInfo.width().coerceAtLeast(1)
        val height = ScreenInfo.height().coerceAtLeast(1)
        capturedWidth = width
        capturedHeight = height
        val reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 4)
        imageReader.set(reader)
        virtualDisplay = mediaProjection.createVirtualDisplay(
            "MiliPyCapture",
            width, height, ScreenInfo.density().toInt().coerceAtLeast(1),
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            reader.surface, null, null
        )
    }

    fun stop() {
        virtualDisplay?.release()
        virtualDisplay = null
        imageReader.getAndSet(null)?.close()
    }

    /**
     * Grab the latest frame as a base64 JPEG map (or null when capture is
     * unavailable), matching the protocol `frame` envelope.
     */
    fun captureFrame(): Map<String, Any>? {
        val reader = imageReader.get() ?: return null
        val image = try {
            reader.acquireLatestImage()
        } catch (_: Exception) {
            return null
        } ?: return null
        return try {
            val bitmap = imageToBitmap(image)
            val bytes = ByteArrayOutputStream().use { out ->
                bitmap.compress(Bitmap.CompressFormat.JPEG, 80, out)
                out.toByteArray()
            }
            mapOf(
                "format" to "jpeg",
                "encoding" to "base64",
                "width" to capturedWidth,
                "height" to capturedHeight,
                "data" to android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP),
            )
        } finally {
            image.close()
        }
    }

    private fun imageToBitmap(image: android.media.Image): Bitmap {
        val planes = image.planes
        val buffer = planes[0].buffer
        val rowStride = planes[0].rowStride
        val pixelStride = planes[0].pixelStride
        val width = image.width
        val height = image.height
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val pixels = IntArray(width * height)
        val bytes = ByteArray(buffer.remaining())
        buffer.get(bytes)
        // RGBA -> ARGB conversion per row stride.
        for (y in 0 until height) {
            val rowOffset = y * rowStride
            for (x in 0 until width) {
                val src = rowOffset + x * pixelStride
                val r = bytes[src].toInt() and 0xFF
                val g = bytes[src + 1].toInt() and 0xFF
                val b = bytes[src + 2].toInt() and 0xFF
                val a = bytes[src + 3].toInt() and 0xFF
                pixels[y * width + x] = (a shl 24) or (r shl 16) or (g shl 8) or b
            }
        }
        bitmap.setPixels(pixels, 0, width, 0, 0, width, height)
        return bitmap
    }
}
