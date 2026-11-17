package com.example.monohighlight

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapShader
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.PorterDuff
import android.graphics.PorterDuffXfermode
import android.graphics.RuntimeShader
import android.graphics.Shader
import android.view.View

/**
 * キャプチャした各ウィンドウの画像を、AGSL シェーダーで
 * 「指定色以外をグレー化」しながら元の位置に描画する全画面ビュー。
 */
class OverlayView(context: Context) : View(context) {

    /** 1 ウィンドウ分の画像。bitmap == null は「描かずに素通しする領域」（セキュアウィンドウ等）。 */
    class Piece(val bitmap: Bitmap?, val left: Int, val top: Int, val width: Int, val height: Int)

    private var pieces: List<Piece> = emptyList()
    private val shader = RuntimeShader(AGSL)
    private val paint = Paint()
    private val clearPaint = Paint().apply { xfermode = PorterDuffXfermode(PorterDuff.Mode.CLEAR) }
    private val loc = IntArray(2)

    init {
        setParams(listOf(Color.BLACK), 0.09f, Color.RED)
    }

    fun setPieces(newPieces: List<Piece>) {
        pieces = newPieces
        invalidate()
    }

    fun setParams(colors: List<Int>, tolerance: Float, highlight: Int?) {
        val enabled = FloatArray(4)
        for (i in 0 until 4) {
            val c = colors.getOrNull(i)
            enabled[i] = if (c != null) 1f else 0f
            shader.setColorUniform("c$i", c ?: Color.BLACK)
        }
        shader.setFloatUniform("en", enabled)
        shader.setFloatUniform("tol", tolerance)
        shader.setFloatUniform("soft", 0.05f)
        shader.setColorUniform("hl", highlight ?: Color.BLACK)
        shader.setFloatUniform("useHl", if (highlight != null) 1f else 0f)
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        // ウィンドウ座標（画面座標）→ このビューの座標
        getLocationOnScreen(loc)
        for (p in pieces) {
            canvas.save()
            canvas.translate((p.left - loc[0]).toFloat(), (p.top - loc[1]).toFloat())
            val bmp = p.bitmap
            if (bmp == null) {
                canvas.drawRect(0f, 0f, p.width.toFloat(), p.height.toFloat(), clearPaint)
            } else {
                shader.setInputShader("img", BitmapShader(bmp, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP))
                paint.shader = shader
                canvas.drawRect(0f, 0f, bmp.width.toFloat(), bmp.height.toFloat(), paint)
            }
            canvas.restore()
        }
    }

    companion object {
        private const val AGSL = """
            uniform shader img;
            layout(color) uniform half4 c0;
            layout(color) uniform half4 c1;
            layout(color) uniform half4 c2;
            layout(color) uniform half4 c3;
            uniform half4 en;   // 各色の有効/無効 (1 or 0)
            uniform half tol;   // この距離以内は完全に元の色
            uniform half soft;  // tol からこの幅でグレーへなめらかに移行
            layout(color) uniform half4 hl; // 一致部分の表示色
            uniform half useHl;             // 1: hl で塗る / 0: 元の色のまま

            half m(half3 rgb, half4 t, half e) {
                return e * (1.0 - smoothstep(tol, tol + soft, distance(rgb, t.rgb)));
            }

            half4 main(float2 p) {
                half4 c = img.eval(p);
                half3 rgb = c.a > 0.0 ? c.rgb / c.a : c.rgb;   // premultiplied → straight
                half g = dot(rgb, half3(0.2126, 0.7152, 0.0722));
                half k = max(max(m(rgb, c0, en.x), m(rgb, c1, en.y)),
                             max(m(rgb, c2, en.z), m(rgb, c3, en.w)));
                half3 keep = useHl > 0.5 ? hl.rgb : rgb;
                return half4(mix(half3(g), keep, k) * c.a, c.a);
            }
        """
    }
}
