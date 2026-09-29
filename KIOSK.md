# Kiosk / Operator Lock Mode

## What it does
Live Camera → **Full Screen** puts the app into locked kiosk mode:
fullscreen, borderless, always-on-top, with the header, log, tab bar and
menu hidden. On **Windows** it also blocks the **Windows key, Alt+Tab and
Alt+F4** system-wide (low-level keyboard hook) and hides the taskbar.
Close attempts on the window are ignored while locked.

## Launching straight into kiosk mode
- Per launch: `CanFallingDetector.exe --kiosk`
- Always: set `"kiosk_autostart": true` in `config/settings.json`

Normal launches (no flag, setting off) are unrestricted, so engineering and
test use is unaffected.

## Exiting (the only in-app path)
`ESC` (or the small on-screen **Exit Kiosk Mode** button) → password dialog
→ correct password unlocks (windowed mode, taskbar/hotkeys restored; the app
keeps running and can then be closed normally). Wrong password or Cancel →
stays locked on Live Camera. The password is not shown anywhere in the UI.
Diagnostics uses the same password (see `app/security.py`).

## What this does NOT and cannot do — please read
- **Ctrl+Alt+Del cannot be blocked by any application.** Windows reserves it.
  It is the guaranteed recovery path for IT (Task Manager → End task, or sign out).
- **Ctrl+Shift+Esc (Task Manager) is deliberately left working**, so authorized
  staff are never forced to power-cycle a production machine.
- A Windows administrator can always terminate the process, log the user off,
  or reboot. Software running as the operator cannot prevent that, and this
  app does not pretend to. Windows shutdown/restart/logoff is never blocked.
- For a hard lockdown, use Windows itself: a dedicated non-admin operator
  account with **Assigned Access / Shell Launcher** (kiosk mode) or Group
  Policy. This app's lock is an in-session layer on top of that, not a
  replacement.
- The password is stored only as a SHA-256 hash, which keeps it out of plain
  sight in the source but is **not strong protection** for a 4-digit PIN
  against someone with the files.
- The keyboard-hook code could not be run in the development sandbox (no
  Windows). **Test it on the real PC before deploying** (checklist below).
- On Linux (Raspberry Pi / Jetson) only fullscreen applies; there is no
  OS-level hotkey blocking.

## IT recovery procedure
1. Normal: ESC → password → unlock.
2. App unresponsive: `Ctrl+Shift+Esc` (or `Ctrl+Alt+Del` → Task Manager) →
   End task `CanFallingDetector.exe`. The keyboard hook disappears with the process.
3. If the taskbar stays hidden after a forced kill: run
   `CanFallingDetector.exe --restore-taskbar` once (no window, no password —
   it only un-hides the taskbar), or Task Manager → File → Run new task →
   `explorer.exe`, or sign out/in.
4. Last resort: reboot / power-cycle.

## Pre-deployment test checklist (on the target Windows PC)
- [ ] `--kiosk` opens Live Camera fullscreen, no title bar/taskbar
- [ ] Win key, Alt+Tab, Alt+F4 do nothing; clicking around can't reach other windows
- [ ] ESC → wrong password → stays locked; right password → unlocks, taskbar back
- [ ] Ctrl+Alt+Del and Ctrl+Shift+Esc still work
- [ ] Force-kill in Task Manager, then confirm `--restore-taskbar` brings the taskbar back
- [ ] Windows Restart/Shut down works while locked
- [ ] Detection, reject, reset and Rejection History behave normally in kiosk mode

## Logo
`app/assets/dotsec_logo.png` (header) and `app/assets/dotsec_icon.ico`
(window/taskbar/.exe icon; set via `--icon` in `.github/workflows/build.yml`).
The icon is the full logo trimmed and centered on a square canvas.
