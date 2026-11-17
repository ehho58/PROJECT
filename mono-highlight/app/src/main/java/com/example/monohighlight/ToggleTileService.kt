package com.example.monohighlight

import android.service.quicksettings.Tile
import android.service.quicksettings.TileService

/** クイック設定パネルからオン/オフするタイル。 */
class ToggleTileService : TileService() {

    override fun onStartListening() = refresh()

    override fun onClick() {
        Prefs.setActive(this, !Prefs.isActive(this))
        refresh()
    }

    private fun refresh() {
        val tile = qsTile ?: return
        tile.state = if (Prefs.isActive(this)) Tile.STATE_ACTIVE else Tile.STATE_INACTIVE
        tile.updateTile()
    }
}
