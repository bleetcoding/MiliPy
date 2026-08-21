package com.milipy.bridge

import android.util.DisplayMetrics
import android.view.WindowManager

/**
 * Runtime screen dimensions of the controlled device, used to translate
 * normalized coordinates into gesture pixels and to fill the `screen`
 * block of observation messages.
 */
object ScreenInfo {

    @Volatile
    private var metrics: Pair<Int, Int> = Pair(1280, 720)

    fun configure(windowManager: WindowManager) {
        val dm = DisplayMetrics()
        windowManager.defaultDisplay?.getRealMetrics(dm)
        metrics = Pair(dm.widthPixels, dm.heightPixels)
    }

    fun width(): Int = metrics.first
    fun height(): Int = metrics.second

    fun density(): Float = try {
        android.content.res.Resources.getSystem().displayMetrics.density
    } catch (_: Exception) {
        2.0f
    }
}
