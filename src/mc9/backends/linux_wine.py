"""Linux backend: MC9 under Wine inside a bubblewrap sandbox, on a virtual display (Xvfb), driven with xdotool.

Layout of the data directory (see `mc9 setup`):  <home>/prefix-pristine, <home>/prefix-work (private copy of the Wine
prefix, created on first use), <home>/exchange (shared as C:\\exchange inside Wine).
"""
from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from .. import workspace
from ..config import config
from ..layout import ANALYSIS_ITEM, L
from .base import Driver

SB_HOME = "/home/sbx"


def prefix_pristine() -> Path:
    return workspace.home() / "prefix-pristine"


def prefix_work() -> Path:
    p = workspace.home() / "prefix-work"
    if not p.exists():
        if not prefix_pristine().exists():
            raise FileNotFoundError(f"{prefix_pristine()} not found: run `mc9 setup /path/to/wine-prefix` first")
        subprocess.run(["cp", "-a", "--reflink=auto", str(prefix_pristine()), str(p)], check=True)
    return p


def reset() -> None:
    """Discard the working Wine prefix; it is re-created from the pristine snapshot on next use."""
    shutil.rmtree(workspace.home() / "prefix-work", ignore_errors=True)


def bwrap_command(args: list[str]) -> list[str]:
    """`bwrap` invocation: no network, empty $HOME, only the Wine prefix copy and the exchange folder are writable."""
    wp, ex = prefix_work(), workspace.exchange()
    return ["bwrap", "--die-with-parent", "--unshare-all", "--new-session",
            "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib", "/lib64",
            "--symlink", "usr/bin", "/bin", "--symlink", "usr/bin", "/sbin",
            "--ro-bind", "/etc", "/etc", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp", "--tmpfs", "/run",
            "--tmpfs", SB_HOME,
            "--bind", str(wp), f"{SB_HOME}/.wine", "--bind", str(ex), f"{SB_HOME}/exchange",
            "--bind", str(ex), f"{SB_HOME}/.wine/drive_c/exchange",
            "--setenv", "HOME", SB_HOME, "--setenv", "WINEPREFIX", f"{SB_HOME}/.wine", "--setenv", "WINEDEBUG", "-all",
            "--setenv", "WINEDLLOVERRIDES", "winemenubuilder.exe=d;mscoree=d;mshtml=d",
            "--setenv", "LANG", "ru_RU.UTF-8", "--setenv", "LC_ALL", "ru_RU.UTF-8", *args]


# Runs inside the sandbox; one command per stdin line, answers "OK" per command.
SERVER = r'''
Xvfb :99 -screen 0 __SCREEN__x24 </dev/null >/dev/null 2>&1 &
export DISPLAY=:99
sleep 2
cd /home/sbx/exchange
wine "__EXE__" "C:\\exchange\\__NAME__.cir" </dev/null >/tmp/w.log 2>&1 &
for i in $(seq 1 60); do xdotool search --name "MC-9" >/dev/null 2>&1 && break; sleep 1; done
sleep 5
echo OK
while IFS= read -r line; do
  read -ra a <<< "$line"
  case "${a[0]}" in
    c)  xdotool mousemove ${a[1]} ${a[2]} click 1;;
    mv) xdotool mousemove ${a[1]} ${a[2]};;
    k)  xdotool key "${a[@]:1}";;
    t)  xdotool type --delay 40 -- "${line#t }";;
    shot) import -window root "/home/sbx/exchange/${a[1]}";;
    quit) wineserver -k 2>/dev/null; kill %1 2>/dev/null; break;;
  esac
  echo OK
done
'''


class Session:
    """Persistent shell inside the sandbox that executes mouse/keyboard/screenshot commands."""

    SCRIPT = SERVER

    def __init__(self, name: str):
        exe = (config.mc9_exe or os.environ.get("MC9_EXE") or workspace.settings().get("mc9_exe")
               or r"C:\Program Files (x86)\mc9g\mc9.exe").replace("\\", "\\\\")
        script = self.SCRIPT.replace("__SCREEN__", config.screen).replace("__NAME__", name).replace("__EXE__", exe)
        if sys.platform == "win32" or sys.platform == "darwin":
            raise RuntimeError("the Wine backend needs Linux; on Windows use backend='windows' (the default there)")
        try:
            self.p = subprocess.Popen(bwrap_command(["bash", "-c", script]), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, text=True, bufsize=1)
        except FileNotFoundError as e:
            raise RuntimeError(f"{e.filename or 'a required tool'} not found - run `mc9 doctor` to see what is missing") from e
        self.q: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()
        self._wait_ok(config.start_timeout)

    def _pump(self) -> None:
        for ln in self.p.stdout:  # type: ignore[union-attr]
            self.q.put(ln.strip())
        self.q.put("EOF")

    def _wait_ok(self, timeout: float) -> None:
        while True:
            try:
                ln = self.q.get(timeout=timeout)
            except queue.Empty:
                raise TimeoutError("MC9 session did not answer") from None
            if ln == "OK":
                return
            if ln == "EOF":
                raise RuntimeError("MC9 session died (is wine / bubblewrap / Xvfb / xdotool installed? try `mc9 doctor`)")

    def cmd(self, line: str, timeout: float = 60) -> None:
        self.p.stdin.write(line + "\n")  # type: ignore[union-attr]
        self.p.stdin.flush()  # type: ignore[union-attr]
        self._wait_ok(timeout)

    def close(self) -> None:
        try:
            self.cmd("quit", 20)
        except Exception:
            pass
        self.p.terminate()


class LinuxWineDriver(Driver):
    def __init__(self, name: str):
        workspace.path(name)
        self.name = name
        self.s = Session(name)

    def _click(self, xy, wait: float = 0.5) -> None:
        self.s.cmd(f"c {xy[0]} {xy[1]}")
        time.sleep(wait)

    def _set_text(self, xy, text: str) -> None:
        self._click(xy, 0.3)
        self.s.cmd("k End shift+Home")       # Win32 edit boxes have no Ctrl+A
        self.s.cmd(f"t {text}")

    def open_analysis(self, key: str) -> None:
        self._click(L.menu_analysis, 1)
        self._click((L.item_x, L.first_item_y + L.item_dy * ANALYSIS_ITEM[key]), 5 if key not in ("dynamic_dc", "dynamic_ac") else 3)

    def press_run(self) -> None:
        self._click(L.run_button, 0.5)

    def confirm_dynamic(self, key: str) -> None:
        self._click(L.dyndc_ok if key == "dynamic_dc" else L.dynac_ok, 3)

    def set_cursors(self, left: str, right: str | None) -> None:
        self._click(L.plot_focus, 1)         # keyboard shortcuts need a focused window
        self.s.cmd("k ctrl+shift+x")
        time.sleep(config.dialog_wait + 1)
        self._set_text(L.cursor_field, left)
        self._click(L.cursor_left, 1)
        if right is not None:
            self._set_text(L.cursor_field, right)
            self._click(L.cursor_right, 1)
        self._click(L.cursor_close, 1)

    def save(self) -> None:
        self.s.cmd("k ctrl+s")
        time.sleep(4)

    def exit_analysis(self) -> None:
        self.s.cmd("k F3")
        time.sleep(2)

    def prepare_capture(self, schematic: bool) -> None:
        if schematic:
            self.s.cmd("k Escape")
            self._click(L.select_tool, 0.5)   # leave component-placement mode (a click would drop a part!)
            self._click(L.blank_canvas, 0.5)  # clear pin hover / selection highlight
        self.s.cmd(f"mv {L.park_mouse[0]} {L.park_mouse[1]}")   # no hover tracker / tooltip
        time.sleep(1)

    def grab(self):
        from PIL import Image
        f = workspace.exchange() / "_grab.png"
        self.s.cmd("shot _grab.png")
        img = Image.open(f).convert("RGB")
        img.load()
        f.unlink(missing_ok=True)
        return img

    def close(self) -> None:
        self.s.close()
