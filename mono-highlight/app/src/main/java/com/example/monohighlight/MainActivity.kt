package com.example.monohighlight

import android.app.Activity
import android.content.ComponentName
import android.content.Intent
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.provider.Settings
import android.text.Editable
import android.text.InputType
import android.text.TextWatcher
import android.util.TypedValue
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.SeekBar
import android.widget.Switch
import android.widget.TextView
import android.view.View

/** 設定画面（レイアウト XML を使わずコードで組み立て）。 */
class MainActivity : Activity() {

    private lateinit var status: TextView
    private lateinit var activeSwitch: Switch
    private val colorFields = mutableListOf<EditText>()
    private val swatches = mutableListOf<View>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = Prefs.of(this)
        val pad = dp(16)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, pad)
        }

        status = TextView(this).apply { textSize = 15f }
        root.addView(status)

        root.addView(Button(this).apply {
            text = "ユーザー補助の設定を開く"
            setOnClickListener { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        })

        activeSwitch = Switch(this).apply {
            text = "モノクロ＋強調を有効にする"
            textSize = 17f
            setPadding(0, dp(12), 0, dp(12))
            setOnCheckedChangeListener { _, checked -> Prefs.setActive(this@MainActivity, checked) }
        }
        root.addView(activeSwitch)

        root.addView(label("強調するカラーコード（最大 ${Prefs.MAX_COLORS} 色、空欄は無効）"))
        val saved = Prefs.colorStrings(this)
        repeat(Prefs.MAX_COLORS) { i ->
            val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            val swatch = View(this)
            val field = EditText(this).apply {
                hint = "#RRGGBB"
                setText(saved.getOrNull(i)?.trim() ?: "")
                inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
                isSingleLine = true
                addTextChangedListener(object : TextWatcher {
                    override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
                    override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
                    override fun afterTextChanged(s: Editable?) = saveColors()
                })
            }
            row.addView(swatch, LinearLayout.LayoutParams(dp(36), dp(36)).apply { marginEnd = dp(12) })
            row.addView(field, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
            root.addView(row)
            colorFields += field
            swatches += swatch
        }

        val tolLabel = label("")
        root.addView(tolLabel)
        root.addView(seek(100, prefs.getInt(Prefs.KEY_TOLERANCE, Prefs.DEFAULT_TOLERANCE)) { v ->
            tolLabel.text = "色の許容範囲: $v（大きいほど近い色も残る）"
            prefs.edit().putInt(Prefs.KEY_TOLERANCE, v).apply()
        })

        val intLabel = label("")
        root.addView(intLabel)
        // 16..500ms
        root.addView(seek(484, prefs.getInt(Prefs.KEY_INTERVAL, Prefs.DEFAULT_INTERVAL) - 16) { v ->
            val ms = v + 16
            intLabel.text = "更新間隔: ${ms}ms（短いほど滑らか・電池消費大）"
            prefs.edit().putInt(Prefs.KEY_INTERVAL, ms).apply()
        })

        root.addView(TextView(this).apply {
            setPadding(0, dp(16), 0, 0)
            text = "・ユーザー補助ボタン／クイック設定タイル「モノクロ強調」でもオン/オフできます\n" +
                "・銀行アプリなど画面保護されたアプリはグレー化されず元の色のまま表示されます\n" +
                "・サイドロードしたアプリは、ユーザー補助で有効にする前に「アプリ情報 → ︙ → 制限付き設定を許可」が必要な場合があります"
        })

        setContentView(ScrollView(this).apply { addView(root, MATCH_PARENT, WRAP_CONTENT) })
        updateSwatches()
    }

    override fun onResume() {
        super.onResume()
        val enabled = isServiceEnabled()
        status.text = if (enabled) "✅ ユーザー補助サービス: 有効" else
            "⚠️ ユーザー補助サービスが無効です。下のボタンから「MonoHighlight」を有効にしてください。"
        activeSwitch.isChecked = Prefs.isActive(this)
        activeSwitch.isEnabled = enabled
    }

    private fun saveColors() {
        val joined = colorFields.joinToString(",") { it.text.toString().trim() }
        Prefs.of(this).edit().putString(Prefs.KEY_COLORS, joined).apply()
        updateSwatches()
    }

    private fun updateSwatches() {
        colorFields.forEachIndexed { i, f ->
            val c = Prefs.parseColor(f.text.toString())
            swatches[i].background = GradientDrawable().apply {
                cornerRadius = dp(6).toFloat()
                setColor(c ?: Color.TRANSPARENT)
                setStroke(dp(1), Color.GRAY)
            }
            f.error = if (c == null && f.text.isNotBlank()) "カラーコードを解釈できません" else null
        }
    }

    private fun isServiceEnabled(): Boolean {
        val me = ComponentName(this, MonoHighlightService::class.java)
        val list = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES) ?: return false
        return list.split(':').any { ComponentName.unflattenFromString(it) == me }
    }

    private fun label(text: String) = TextView(this).apply {
        this.text = text
        setPadding(0, dp(16), 0, dp(4))
    }

    private fun seek(max: Int, initial: Int, onChange: (Int) -> Unit) = SeekBar(this).apply {
        this.max = max
        progress = initial.coerceIn(0, max)
        onChange(progress)
        setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(s: SeekBar?, v: Int, fromUser: Boolean) = onChange(v)
            override fun onStartTrackingTouch(s: SeekBar?) {}
            override fun onStopTrackingTouch(s: SeekBar?) {}
        })
    }

    private fun dp(v: Int) = TypedValue.applyDimension(
        TypedValue.COMPLEX_UNIT_DIP, v.toFloat(), resources.displayMetrics
    ).toInt()
}
