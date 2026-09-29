"""
kiosk_lock.py
--------------
Windows-only OS-level lockdown used by Live Camera's kiosk/fullscreen
mode (see camera_tab.py). While engaged, blocks the Windows key, Alt+Tab,
and Alt+F4 at the keyboard-hook level (so they never reach the Windows
shell), and hides the taskbar. Released automatically when kiosk mode is
exited (correct password entered) or the app closes.

NOT TESTED ON REAL WINDOWS HARDWARE. This module uses raw ctypes calls
into user32.dll/kernel32.dll, written carefully against the standard,
well-documented WH_KEYBOARD_LL low-level-keyboard-hook pattern (with
explicit argtypes/restype set on every Win32 call -- the single most
common cause of these hooks silently failing on 64-bit Python is
*omitting* that). But there is no way to run or verify actual Win32 API
behavior from this environment. Verify engage()/release() on a real
Windows machine before relying on this for production kiosk deployment --
exactly the same caveat this project already gives for the Controller .ino
files, for the same underlying reason (no target hardware/OS available
here to test against).

HONEST LIMITS -- READ BEFORE RELYING ON THIS:
- This is a user-mode, in-process hook. It only affects the current
  interactive desktop session for as long as this application's process
  is running. If the process is killed outright (Task Manager, `taskkill`,
  a remote admin tool, power-cycling the machine), the hook is gone and
  the taskbar/normal desktop access return immediately. That's expected,
  not a bug -- no application can prevent an administrator from
  terminating its own process; see the kiosk-mode docstring in
  camera_tab.py.
- Ctrl+Alt+Del cannot be intercepted by ANY user-mode application on
  Windows, by OS design (it's the "Secure Attention Sequence"). That's not
  a gap here -- it's the built-in, un-bypassable recovery path IT should
  use if a locked machine ever needs attention outside the documented
  in-app password.
- Ctrl+Shift+Esc (the direct Task Manager shortcut) is DELIBERATELY left
  unblocked, for the same reason: so IT always has an immediate way back
  into Windows without power-cycling a production machine. This is a
  deliberate design choice, not an oversight.
- On non-Windows platforms (this project also targets Raspberry Pi /
  Jetson Linux -- see RASPBERRY_PI.md / JETSON.md), none of the OS hotkey
  blocking below is available; KioskGuard.engage()/release() silently
  no-op there and only plain fullscreen applies.
"""

import sys
import ctypes

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    WH_KEYBOARD_LL = 13
    WM_KEYDOWN = 0x0100
    WM_SYSKEYDOWN = 0x0104

    VK_LWIN = 0x5B
    VK_RWIN = 0x5C
    VK_TAB = 0x09
    VK_F4 = 0x73
    VK_MENU = 0x12  # Alt

    SW_HIDE = 0
    SW_SHOWNORMAL = 1

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

    # Explicit argtypes/restype on every call below -- omitting these is
    # the #1 cause of these hooks silently misbehaving on 64-bit Python.
    user32.SetWindowsHookExW.restype = wintypes.HHOOK
    user32.SetWindowsHookExW.argtypes = [
        ctypes.c_int, LowLevelKeyboardProc, wintypes.HINSTANCE, wintypes.DWORD]
    user32.CallNextHookEx.restype = ctypes.c_int
    user32.CallNextHookEx.argtypes = [
        wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]


class KioskGuard:
    """
    Engages/releases the OS-level lockdown described above. Safe to call
    engage()/release() on any platform -- everything is a no-op off
    Windows, and every Win32 call is wrapped so a failure here logs a
    warning and degrades to "plain fullscreen, no OS-level hotkey
    blocking" rather than crashing the app.
    """

    def __init__(self, log_fn=None):
        self.log = log_fn or (lambda msg: None)
        self._hook_handle = None
        self._hook_proc = None  # must keep a reference alive -- ctypes
        # callback objects get garbage-collected otherwise, which crashes
        # the hook (or worse, corrupts the call) the moment it fires.
        self._taskbar_hwnd = None
        self._engaged = False

    @property
    def engaged(self):
        return self._engaged

    @staticmethod
    def restore_taskbar():
        """Unconditionally un-hides the Windows taskbar. Used by the
        `--restore-taskbar` recovery flag (see main.py / KIOSK.md) for the
        case where the app was force-killed while in kiosk mode and never
        got to restore it itself. No-op off Windows."""
        if not IS_WINDOWS:
            return
        try:
            hwnd = user32.FindWindowW("Shell_TrayWnd", None)
            if hwnd:
                user32.ShowWindow(hwnd, SW_SHOWNORMAL)
        except Exception:
            pass

    def engage(self):
        if not IS_WINDOWS or self._engaged:
            return
        try:
            self._hook_proc = LowLevelKeyboardProc(self._low_level_handler)
            self._hook_handle = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL, self._hook_proc, kernel32.GetModuleHandleW(None), 0)
            if not self._hook_handle:
                self.log(
                    "WARNING: kiosk lock could not install the keyboard hook -- "
                    "the Windows key/Alt+Tab/Alt+F4 will NOT be blocked. Fullscreen "
                    "will still apply. Verify this on the target machine before "
                    "relying on it for operator lockdown.")
        except Exception as e:
            self.log(f"WARNING: kiosk keyboard hook failed to install: {e}")
            self._hook_handle = None
            self._hook_proc = None

        try:
            self._taskbar_hwnd = user32.FindWindowW("Shell_TrayWnd", None)
            if self._taskbar_hwnd:
                user32.ShowWindow(self._taskbar_hwnd, SW_HIDE)
        except Exception as e:
            self.log(f"WARNING: could not hide the taskbar: {e}")
            self._taskbar_hwnd = None

        self._engaged = True

    def release(self):
        if not IS_WINDOWS:
            return
        try:
            if self._hook_handle:
                user32.UnhookWindowsHookEx(self._hook_handle)
        except Exception as e:
            self.log(f"WARNING: error removing kiosk keyboard hook: {e}")
        finally:
            self._hook_handle = None
            self._hook_proc = None

        try:
            if self._taskbar_hwnd:
                user32.ShowWindow(self._taskbar_hwnd, SW_SHOWNORMAL)
        except Exception as e:
            self.log(f"WARNING: error restoring the taskbar: {e}")
        finally:
            self._taskbar_hwnd = None

        self._engaged = False

    def _low_level_handler(self, nCode, wParam, lParam):
        try:
            if nCode == 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                kbd = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = kbd.vkCode
                alt_down = (user32.GetAsyncKeyState(VK_MENU) & 0x8000) != 0
                # Block: Windows key, Alt+Tab, Alt+F4.
                # Deliberately NOT blocked: Ctrl+Alt+Del (impossible to
                # hook, by Windows design) and Ctrl+Shift+Esc (Task
                # Manager) -- see module docstring for why that's
                # intentional, not an oversight.
                if vk in (VK_LWIN, VK_RWIN):
                    return 1
                if alt_down and vk == VK_TAB:
                    return 1
                if alt_down and vk == VK_F4:
                    return 1
        except Exception:
            pass  # never let a hook-callback error take down the app
        return user32.CallNextHookEx(self._hook_handle, nCode, wParam, lParam)
