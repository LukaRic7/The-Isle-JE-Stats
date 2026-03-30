#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent(true)

#Include jxon.ahk

; Settings, can not be changed when compiled obviously!
C_OVERLAY := { monitor: 1, xPct: 0.9, yPct: 0.65 }
C_COLORS := {
    overlay: '1E1E1E', health: 'ff4c4c', growth: '7cfc00',
    hunger: 'ffa500', thirst: '00ffff'
}

; Set the tray
Tray := A_TrayMenu
Tray.Delete()
Tray.Add('TIJE Overlay - Exit', (*) => ExitApp())
Tray.Default := 'TIJE Overlay - Exit'

; Create the GUI object
Overlay := Gui("+AlwaysOnTop +ToolWindow -Caption +E0x80000 +E0x20")
Overlay.BackColor := C_COLORS.overlay
WinSetTransparent(200, Overlay.Hwnd)

; Update info
Overlay.SetFont('s11 cWhite')
update_est := Overlay.AddText('x2 y2 h20 w120', 'Updating in: -')

; Balance info
balance_gui := Overlay.AddText('x+2 y2 h20 w116 Center', '$0')

; Create the rows
health := GUI_AddRow('Health', C_COLORS.health, 24)
growth := GUI_AddRow('Growth', C_COLORS.growth, 46)
hunger := GUI_AddRow('Hunger', C_COLORS.hunger, 68)
thirst := GUI_AddRow('Thirst', C_COLORS.thirst, 90)

; Calculate the screen position, and display the GUI
MonitorGet(C_OVERLAY.monitor, &mLeft, &mTop, &mRight, &mBottom)
xPos := (mRight - mLeft) * C_OVERLAY.xPct
yPos := (mBottom - mTop) * C_OVERLAY.yPct
Overlay.Show('x' . xPos . ' y' . yPos . ' w242 h112')

; Mainloop, read daemon output file every second
while true {
    GUI_UpdateValues()
    Sleep(1000)
}

/**
 * Replace the sign of a value.
 * @param {Number} val Input value.
 * @param {String} neg Replaces negative sign.
 * @param {String} pos Replaces positive sign.
 * @returns {String} Formatted value.
 */
ReplaceSign(val, neg, pos) {
    ; If exactly zero, don't add any sign
    if val == 0
        return val

    ; Replace sign and return absolute
    return (val > 0 ? pos : neg) . Format('{:.1f}', Abs(val))
}

/**
 * Create a row containing the columns: Percent, Delta & EST
 * @param {String} label Display label for the row.
 * @param {String} color Color of the row text.
 * @param {Number} startY Starting Y position in pixels unit.
 * @returns {Object} The column GUI objects in the row.
 */
GUI_AddRow(label, color, startY) {
    Overlay.SetFont('s12 c' . color)
    Overlay.AddText('x2 y' . startY . ' w55 h20', label . ':')

    pct   := Overlay.AddText('x+5 yp w45 hp', '-')
    delta := Overlay.AddText('x+5 yp w70 hp', '-')
    est   := Overlay.AddText('x+5 yp w50 hp', '-')

    return { pct: pct, delta: delta, est: est }
}

/**
 * Update the GUI rows with the daemons values.
 */
GUI_UpdateValues() {
    ; Read and parse deamons values
    fileContent := FileRead('./output.json')
    data := Jxon_Load(&fileContent)

    ; Set next update countdown
    next_upd := data.Get('next-update-unix')
    if next_upd {
        unix := DateDiff(A_NowUTC, '19700101000000', 'Seconds')
        update_est.Value := 'Updating In: ' . Round(next_upd - unix) . 's'
    }

    ; Set the balance
    balance := data.Get('balance')
    if balance {
        balance_gui.Value := '$' . balance
    }

    ; Set the currents
    current := data.Get('current')
    if current {
        health.pct.Value := Round(current.Get('Health') * 100) . '%'
        growth.pct.Value := Round(current.Get('Growth') * 100) . '%'
        hunger.pct.Value := Round(current.Get('Hunger') * 100) . '%'
        thirst.pct.Value := Round(current.Get('Thirst') * 100) . '%'
    }

    ; Set the deltas
    delta := data.Get('delta-per-min')
    if delta {
        health.delta.Value := ReplaceSign(Round(delta.Get('Health') * 100, 1), '↓', '⤒') . '%/m'
        growth.delta.Value := ReplaceSign(Round(delta.Get('Growth') * 100, 1), '↓', '↑') . '%/m'
        hunger.delta.Value := ReplaceSign(Round(delta.Get('Hunger') * 100, 1), '↓', '↑') . '%/m'
        thirst.delta.Value := ReplaceSign(Round(delta.Get('Thirst') * 100, 1), '↓', '↑') . '%/m'
    }

    ; Set the ESTs
    est := data.Get('est-time-min')
    if est {
        health.est.Value := '⤒' . Round(est.Get('Health')) . 'm'
        growth.est.Value := '⤒' . Round(est.Get('Growth')) . 'm'
        hunger.est.Value := '⤓' . Round(est.Get('Hunger')) . 'm'
        thirst.est.Value := '⤓' . Round(est.Get('Thirst')) . 'm'
    }
}