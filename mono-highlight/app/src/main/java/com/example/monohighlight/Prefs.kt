package com.example.monohighlight

import android.content.Context
import android.content.SharedPreferences
import android.graphics.Color

/** 設定値の保存場所。Activity / タイル / サービスは同じプロセスなので変更リスナーで連携する。 */
object Prefs {
    private const val NAME = "settings"

    const val KEY_ACTIVE = "active"
    const val KEY_COLORS = "colors"       // "#FF0000,#00A0E9" のようなカンマ区切り
    const val KEY_TOLERANCE = "tolerance" // 0..100
    const val KEY_INTERVAL = "interval"   // キャプチャ間隔 ms
    const val KEY_HIGHLIGHT = "highlight" // 一致した部分の表示色（空欄なら元の色のまま）

    const val MAX_COLORS = 4
    const val DEFAULT_TOLERANCE = 15
    const val DEFAULT_INTERVAL = 50

    fun of(ctx: Context): SharedPreferences =
        ctx.applicationContext.getSharedPreferences(NAME, Context.MODE_PRIVATE)

    fun isActive(ctx: Context) = of(ctx).getBoolean(KEY_ACTIVE, false)

    fun setActive(ctx: Context, active: Boolean) =
        of(ctx).edit().putBoolean(KEY_ACTIVE, active).apply()

    fun colorStrings(ctx: Context): List<String> =
        (of(ctx).getString(KEY_COLORS, "#000000") ?: "").split(',')

    /** 解釈できたカラーコードだけを返す（最大 MAX_COLORS 個）。 */
    fun colors(ctx: Context): List<Int> =
        colorStrings(ctx).mapNotNull { parseColor(it) }.take(MAX_COLORS)

    /** 0..100 のスライダー値を RGB 空間（0..1）での距離に変換。 */
    fun toleranceDistance(ctx: Context): Float =
        of(ctx).getInt(KEY_TOLERANCE, DEFAULT_TOLERANCE) / 100f * 0.6f

    fun highlightString(ctx: Context): String =
        of(ctx).getString(KEY_HIGHLIGHT, "#FF0000") ?: ""

    /** null = 元の色のまま残す */
    fun highlightColor(ctx: Context): Int? = parseColor(highlightString(ctx))

    fun intervalMs(ctx: Context): Long =
        of(ctx).getInt(KEY_INTERVAL, DEFAULT_INTERVAL).toLong()

    fun parseColor(raw: String): Int? {
        var s = raw.trim()
        if (s.isEmpty()) return null
        if (!s.startsWith("#")) s = "#$s"
        // #RGB の短縮表記にも対応
        if (s.length == 4) s = "#" + s.drop(1).map { "$it$it" }.joinToString("")
        return try {
            Color.parseColor(s) or 0xFF000000.toInt()
        } catch (_: IllegalArgumentException) {
            null
        }
    }
}
