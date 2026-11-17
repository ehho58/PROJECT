package com.example.monohighlight

import android.accessibilityservice.AccessibilityButtonController
import android.accessibilityservice.AccessibilityService
import android.content.SharedPreferences
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.graphics.Rect
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import android.util.Log
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityWindowInfo

/**
 * 仕組み:
 *  1. getWindows() で画面上のウィンドウ一覧を取得
 *  2. 自分のオーバーレイ以外を takeScreenshotOfWindow() でウィンドウ単位にキャプチャ
 *     （画面全体ではなくウィンドウ単位なので、自分のオーバーレイが写り込まない）
 *  3. OverlayView（TYPE_ACCESSIBILITY_OVERLAY, タッチ素通し）にシェーダー付きで描画
 *  4. 一定間隔で繰り返す
 */
class MonoHighlightService : AccessibilityService(), SharedPreferences.OnSharedPreferenceChangeListener {

    private val handler = Handler(Looper.getMainLooper())
    private var windowManager: WindowManager? = null
    private var overlay: OverlayView? = null

    private var capturing = false
    private var frameStartedAt = 0L
    /** 一時的な失敗時に前回の画像を使い回すためのキャッシュ（windowId → Piece） */
    private var lastPieces = mapOf<Int, OverlayView.Piece>()

    private val buttonCallback = object : AccessibilityButtonController.AccessibilityButtonCallback() {
        override fun onClicked(controller: AccessibilityButtonController) {
            Prefs.setActive(this@MonoHighlightService, !Prefs.isActive(this@MonoHighlightService))
        }
    }

    private val loop = Runnable { captureFrame() }

    override fun onServiceConnected() {
        windowManager = getSystemService(WindowManager::class.java)
        accessibilityButtonController.registerAccessibilityButtonCallback(buttonCallback)
        Prefs.of(this).registerOnSharedPreferenceChangeListener(this)
        if (Prefs.isActive(this)) showOverlay()
    }

    override fun onDestroy() {
        hideOverlay()
        Prefs.of(this).unregisterOnSharedPreferenceChangeListener(this)
        accessibilityButtonController.unregisterAccessibilityButtonCallback(buttonCallback)
        super.onDestroy()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // ウィンドウ構成が変わったら待たずに次のフレームを撮る
        if (event?.eventType == AccessibilityEvent.TYPE_WINDOWS_CHANGED && overlay != null && !capturing) {
            handler.removeCallbacks(loop)
            handler.post(loop)
        }
    }

    override fun onInterrupt() {}

    override fun onSharedPreferenceChanged(prefs: SharedPreferences, key: String?) {
        when (key) {
            Prefs.KEY_ACTIVE -> if (Prefs.isActive(this)) showOverlay() else hideOverlay()
            Prefs.KEY_COLORS, Prefs.KEY_TOLERANCE, Prefs.KEY_HIGHLIGHT -> applyParams()
        }
    }

    // ---------------------------------------------------------------- overlay

    private fun showOverlay() {
        if (overlay != null) return
        val view = OverlayView(this)
        val lp = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or
                WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED,
            PixelFormat.TRANSLUCENT,
        ).apply {
            layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
            setFitInsetsTypes(0)
            title = "MonoHighlightOverlay"
        }
        windowManager?.addView(view, lp)
        overlay = view
        applyParams()
        handler.post(loop)
    }

    private fun hideOverlay() {
        handler.removeCallbacks(loop)
        overlay?.let { windowManager?.removeViewImmediate(it) }
        overlay = null
        lastPieces = emptyMap()
        capturing = false
    }

    private fun applyParams() {
        overlay?.setParams(Prefs.colors(this), Prefs.toleranceDistance(this), Prefs.highlightColor(this))
    }

    // ---------------------------------------------------------------- capture

    private fun captureFrame() {
        val view = overlay ?: return
        if (capturing) return
        if (!getSystemService(PowerManager::class.java).isInteractive) {
            // 画面オフ中は休む
            handler.postDelayed(loop, 1000)
            return
        }

        val targets = windows
            .filter { it.type != AccessibilityWindowInfo.TYPE_ACCESSIBILITY_OVERLAY &&
                it.type != AccessibilityWindowInfo.TYPE_MAGNIFICATION_OVERLAY }
            .sortedBy { it.layer } // 下のウィンドウから描く

        if (targets.isEmpty()) {
            scheduleNext()
            return
        }

        capturing = true
        frameStartedAt = SystemClock.uptimeMillis()
        val results = arrayOfNulls<OverlayView.Piece>(targets.size)
        var remaining = targets.size
        val rect = Rect()

        targets.forEachIndexed { index, win ->
            win.getBoundsInScreen(rect)
            val left = rect.left
            val top = rect.top
            val w = rect.width()
            val h = rect.height()
            val id = win.id

            takeScreenshotOfWindow(id, mainExecutor, object : TakeScreenshotCallback {
                override fun onSuccess(result: ScreenshotResult) {
                    val buffer = result.hardwareBuffer
                    val bmp = Bitmap.wrapHardwareBuffer(buffer, result.colorSpace)
                    buffer.close() // Bitmap 側が参照を保持するので閉じてよい
                    results[index] = OverlayView.Piece(bmp, left, top, w, h)
                    if (--remaining == 0) finishFrame(view, targets, results)
                }

                override fun onFailure(errorCode: Int) {
                    results[index] = when (errorCode) {
                        // 銀行アプリ等。グレー化できないので、その領域は素通し（元の色のまま）にする
                        ERROR_TAKE_SCREENSHOT_SECURE_WINDOW -> OverlayView.Piece(null, left, top, w, h)
                        // 一時的な失敗は前回の画像で代用
                        else -> {
                            Log.d(TAG, "screenshot failed: window=$id code=$errorCode")
                            lastPieces[id]?.takeIf { it.left == left && it.top == top }
                        }
                    }
                    if (--remaining == 0) finishFrame(view, targets, results)
                }
            })
        }
    }

    private fun finishFrame(
        view: OverlayView,
        targets: List<AccessibilityWindowInfo>,
        results: Array<OverlayView.Piece?>,
    ) {
        capturing = false
        if (overlay !== view) return // 途中で停止された
        val map = HashMap<Int, OverlayView.Piece>()
        val list = ArrayList<OverlayView.Piece>(targets.size)
        targets.forEachIndexed { i, win ->
            results[i]?.let {
                list += it
                if (it.bitmap != null) map[win.id] = it
            }
        }
        lastPieces = map
        view.setPieces(list)
        scheduleNext()
    }

    private fun scheduleNext() {
        if (overlay == null) return
        val elapsed = SystemClock.uptimeMillis() - frameStartedAt
        handler.postDelayed(loop, (Prefs.intervalMs(this) - elapsed).coerceAtLeast(0))
    }

    companion object {
        private const val TAG = "MonoHighlight"
    }
}
