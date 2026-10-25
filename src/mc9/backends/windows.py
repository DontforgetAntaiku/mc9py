"""Windows backend: drives a native MC9 with the Win32 API (ctypes + Pillow only).

Language independent on purpose: analyses are opened with MC9's keyboard accelerators (Alt+1 transient, Alt+2 AC, ...),
run with F2, closed with F3, cursors with Ctrl+Shift+X; dialog buttons/edit boxes are found by class and order.
Only toolbar icons (identical in every language) are clicked by coordinate. The MC9 window is moved to (0,0) and
resized to 1900x980 so the capture regions in `layout.py` apply. Use 100 % display scaling.

This module is also exercised on Linux by running Windows Python inside Wine (see tools/test_windows_backend.sh).
"""
from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import time
from ctypes import wintypes as wt
from pathlib import Path

from .. import workspace
from ..config import config
from ..layout import ANALYSIS_KEYS, L
from .base import Driver

if sys.platform != "win32":              # allow importing for documentation / unit tests on other systems
    raise ImportError("the Windows backend only works on Windows (or Windows Python under Wine)")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:
    user32.SetProcessDPIAware()
except Exception:                         # pragma: no cover
    pass

ULONG_PTR = ctypes.c_size_t
WM_SETTEXT, BM_CLICK, WM_CLOSE = 0x000C, 0x00F5, 0x0010
SWP_NOZORDER, SWP_SHOWWINDOW = 0x0004, 0x0040
SW_RESTORE = 9
VK = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12, "esc": 0x1B, "escape": 0x1B, "return": 0x0D, "enter": 0x0D, "end": 0x23,
      "home": 0x24, "tab": 0x09, **{f"f{i}": 0x6F + i for i in range(1, 13)}}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _U)]


WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wt.LPARAM]
user32.EnumChildWindows.argtypes = [wt.HWND, WNDENUMPROC, wt.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsWindowEnabled.argtypes = [wt.HWND]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.SendMessageTimeoutW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM, wt.UINT, wt.UINT, ctypes.POINTER(ctypes.c_size_t)]
user32.SendMessageTimeoutW.restype = ctypes.c_ssize_t
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.GetDlgItem.argtypes = [wt.HWND, ctypes.c_int]
user32.GetDlgItem.restype = wt.HWND
user32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int]


def _msg(hwnd, msg: int, wparam: int = 0, lparam: int = 0, timeout_ms: int = 4000) -> None:
    """SendMessage that cannot hang: a button that opens a modal dialog would block a plain SendMessage forever."""
    res = ctypes.c_size_t()
    user32.SendMessageTimeoutW(hwnd, msg, wparam, lparam, 2, timeout_ms, ctypes.byref(res))   # SMTO_ABORTIFHUNG


def _text(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def _cls(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _rect(hwnd) -> tuple[int, int, int, int]:
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def find_mc9() -> str:
    """Locate mc9.exe: config.mc9_exe, PATH, or the usual install folders."""
    if config.mc9_exe:
        return config.mc9_exe
    found = shutil.which("mc9.exe")
    cands = [found] if found else []
    for base in (os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), os.environ.get("ProgramFiles", r"C:\Program Files"), "C:\\"):
        for sub in ("Micro-Cap 9", "Spectrum Software\\MC9", "Spectrum Software\\Micro-Cap 9", "mc9g", "MC9", "mc9"):
            cands.append(str(Path(base) / sub / "mc9.exe"))
    for c in cands:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError("mc9.exe not found; set it: mc9.config.mc9_exe = r'C:\\path\\to\\mc9.exe'")


class WindowsDriver(Driver):
    def __init__(self, name: str):
        self.name = name
        cir = workspace.path(name)
        self.proc = subprocess.Popen([find_mc9(), str(cir)], cwd=str(cir.parent))
        self.hwnd = self._wait_main_window(config.start_timeout)
        self._place()
        time.sleep(3)

    # ---- windows -----------------------------------------------------------------------------
    def _windows(self, children_of=None) -> list:
        out = []
        pid = self.proc.pid

        def cb(h, _):
            p = wt.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(p))
            if p.value == pid:
                out.append(h)
            return True
        user32.EnumWindows(WNDENUMPROC(cb), 0)
        return out

    def _wait_main_window(self, timeout: float):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError(f"MC9 exited immediately (code {self.proc.returncode})")
            best = None
            for h in self._windows():
                l, t, r, b = _rect(h)
                if user32.IsWindowVisible(h) and _text(h) and _cls(h) != "#32770" and (r - l) > 600:
                    best = h
            if best:
                return best
            time.sleep(0.5)
        raise TimeoutError("MC9 main window did not appear")

    def _place(self) -> None:
        user32.ShowWindow(self.hwnd, SW_RESTORE)
        user32.SetWindowPos(self.hwnd, 0, 0, 0, L.window[0], L.window[1], SWP_NOZORDER | SWP_SHOWWINDOW)
        user32.SetForegroundWindow(self.hwnd)
        self.origin = _rect(self.hwnd)[:2]

    def _dialogs(self) -> list:
        return [h for h in self._windows() if h != self.hwnd and user32.IsWindowVisible(h) and _cls(h) == "#32770"]

    def _wait_dialog(self, before: set, timeout: float = 8):
        t0 = time.time()
        while time.time() - t0 < timeout:
            new = [h for h in self._dialogs() if h not in before]
            if new:
                return new[-1]
            time.sleep(0.3)
        raise TimeoutError("expected MC9 dialog did not appear")

    @staticmethod
    def _controls(dlg) -> list[tuple]:
        out = []

        def cb(h, _):
            out.append((h, _cls(h), _text(h), bool(user32.IsWindowVisible(h)), bool(user32.IsWindowEnabled(h))))
            return True
        user32.EnumChildWindows(dlg, WNDENUMPROC(cb), 0)
        return out

    # ---- input --------------------------------------------------------------------------------
    def _send(self, inputs: list) -> None:
        arr = (INPUT * len(inputs))(*inputs)
        user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

    def _key(self, combo: str) -> None:
        vks = []
        for part in combo.lower().split("+"):
            vks.append(VK[part] if part in VK else ord(part.upper()))
        for flags in (0, 2):      # key down, then key up in reverse order
            seq = vks if flags == 0 else list(reversed(vks))
            self._send([INPUT(1, _U(ki=KEYBDINPUT(v, 0, flags, 0, 0))) for v in seq])
            time.sleep(0.06)

    def _mouse_to(self, x: int, y: int) -> None:
        user32.SetCursorPos(self.origin[0] + x, self.origin[1] + y)

    def _click(self, xy, wait: float = 0.5) -> None:
        self._mouse_to(*xy)
        time.sleep(0.15)
        self._send([INPUT(0, _U(mi=MOUSEINPUT(0, 0, 0, 2, 0, 0)))])
        time.sleep(0.05)
        self._send([INPUT(0, _U(mi=MOUSEINPUT(0, 0, 0, 4, 0, 0)))])
        time.sleep(wait)

    def _focus(self) -> None:
        user32.SetForegroundWindow(self.hwnd)
        self._click(L.title_bar, 0.3)        # harmless click that gives MC9 keyboard focus

    # ---- Driver interface ---------------------------------------------------------------------
    def open_analysis(self, key: str) -> None:
        self._focus()
        before = set(self._dialogs())
        self._key(ANALYSIS_KEYS[key])
        time.sleep(3)
        if key in ("dynamic_dc", "dynamic_ac"):
            self._dyn_dialog = self._wait_dialog(before)

    def press_run(self) -> None:
        self._focus()
        self._key("f2")
        time.sleep(0.5)

    def confirm_dynamic(self, key: str) -> None:
        dlg = getattr(self, "_dyn_dialog", None) or self._wait_dialog(set())
        ok = user32.GetDlgItem(dlg, 1)                       # IDOK
        if ok:
            _msg(ok, BM_CLICK)
        else:                                                # fall back to the first enabled button
            btn = next(c for c in self._controls(dlg) if c[1].lower() == "button" and c[3] and c[4])
            _msg(btn[0], BM_CLICK)
        self._dyn_dialog = None
        time.sleep(3)

    def set_cursors(self, left: str, right: str | None) -> None:
        self._focus()
        self._click(L.plot_focus, 0.5)
        before = set(self._dialogs())
        self._key("ctrl+shift+x")
        dlg = self._wait_dialog(before)
        ctrls = self._controls(dlg)
        edit = next(c[0] for c in ctrls if c[1].lower() == "edit" and c[3])
        buttons = [c for c in ctrls if c[1].lower() == "button" and c[3] and c[4]]
        by_text = {c[2].strip().lower(): c[0] for c in buttons}
        b_left, b_right, b_close = by_text.get("left", buttons[0][0]), by_text.get("right", buttons[1][0]), by_text.get("close", buttons[2][0])

        def put(text: str) -> None:
            buf = ctypes.create_unicode_buffer(text)            # must stay alive while the message is processed
            _msg(edit, WM_SETTEXT, 0, ctypes.addressof(buf))
        put(left)
        _msg(b_left, BM_CLICK)
        time.sleep(1)
        if right is not None:
            put(right)
            _msg(b_right, BM_CLICK)
            time.sleep(1)
        _msg(b_close, BM_CLICK)
        time.sleep(1)

    def exit_analysis(self) -> None:
        self._focus()
        self._key("f3")
        time.sleep(2)

    def prepare_capture(self, schematic: bool) -> None:
        if schematic:
            self._focus()
            self._key("escape")
            self._click(L.select_tool, 0.5)
            self._click(L.blank_canvas, 0.5)
        user32.SetCursorPos(self.origin[0] + L.window[0] - 2, self.origin[1] + L.window[1] - 2)
        time.sleep(1)

    def grab(self):
        from PIL import ImageGrab
        l, t = _rect(self.hwnd)[:2]
        return ImageGrab.grab(bbox=(l, t, l + L.window[0], t + L.window[1])).convert("RGB")

    def close(self) -> None:
        """Terminate MC9 (nothing is ever saved, so no 'save changes?' dialog is wanted)."""
        if self.proc.poll() is None:
            self.proc.kill()
            try:
                self.proc.wait(timeout=10)
            except Exception:
                pass
