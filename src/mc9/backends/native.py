"""The native engine: MC9 runs with ``mc9hook.dll`` inside it and is driven by posted commands and dialog messages.

No mouse, no keyboard and no screen coordinates are used (the only OS-level calls are starting MC9 and capturing its
window). It is a separate engine from the click drivers (`linux_wine.py`, `windows.py`): a session uses one or the other.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from .. import native, workspace
from ..config import config
from ..layout import L
from .base import Driver

NATIVE_SERVER = r'''
Xvfb :99 -screen 0 __SCREEN__x24 </dev/null >/dev/null 2>&1 &
export DISPLAY=:99
sleep 2
cd /home/sbx/exchange
__LAUNCH__ </dev/null >/home/sbx/exchange/launch.log 2>&1 &
echo OK
while IFS= read -r line; do
  read -ra a <<< "$line"
  case "${a[0]}" in
    shot) import -window root "/home/sbx/exchange/${a[1]}";;
    quit) wineserver -k 2>/dev/null; kill %1 2>/dev/null; break;;
  esac
  echo OK
done
'''


def _parse(text: str) -> list[list[str]]:
    return [ln.split("|") for ln in text.splitlines() if ln.strip()]


class NativeDriver(Driver):
    name = "native"

    def __init__(self, name: str):
        self.name = name
        self.session = None
        self.proc = None
        self._dyn = None
        workspace.path(name)
        folder = native.install()
        self.hook = native.Hook()
        self._start(name, folder)
        try:
            self.hook.wait(config.start_timeout)
            self.cmd = native.Commands(self.hook)
            self._wait_frame(config.start_timeout)
            self.hook.send("place", f"0 0 {L.window[0]} {L.window[1]}")
        except Exception:
            self.close()
            raise
        time.sleep(1)

    # ---- start / stop (the only OS-specific part, besides capture) ----------------------------
    def _start(self, name: str, folder: Path) -> None:
        for stale in ("hook.req", "hook.resp"):
            (folder / stale).unlink(missing_ok=True)
        if sys.platform == "win32":
            from .windows import find_mc9
            cir = workspace.path(name)
            env = dict(os.environ, MC9HOOK_DIR=str(folder))
            self.proc = subprocess.Popen([find_mc9(), str(cir)], cwd=str(cir.parent), env=env)
            time.sleep(3)
            subprocess.run([str(folder / "mc9launch.exe"), "--attach", str(self.proc.pid), str(folder / "mc9hook.dll")],
                           check=True, capture_output=True, timeout=60)
        else:
            from .linux_wine import Session
            exe = (config.mc9_exe or os.environ.get("MC9_EXE") or workspace.settings().get("mc9_exe")
                   or r"C:\Program Files (x86)\mc9g\mc9.exe").replace("\\", "\\\\")
            launch = (f'wine "C:\\\\exchange\\\\mc9launch.exe" "C:\\\\exchange\\\\mc9hook.dll" "{exe}" '
                      f'"C:\\\\exchange\\\\{name}.cir"')

            class _NativeSession(Session):
                SCRIPT = NATIVE_SERVER.replace("__LAUNCH__", launch)
            self.session = _NativeSession(name)

    def _wait_frame(self, timeout: float) -> None:
        end = time.time() + timeout
        while time.time() < end:
            try:
                self.hook.send("frame", timeout=3)
                return
            except native.HookError:
                time.sleep(0.5)
        raise TimeoutError("MC9 main window did not appear" + self._dialog_report())

    def close(self) -> None:
        try:
            self.hook.send("quit", timeout=3)
        except Exception:
            pass
        if self.session is not None:
            self.session.close()
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()

    # ---- dialogs ------------------------------------------------------------------------------
    def _dialogs(self) -> dict[str, str]:
        return {h: t for h, t, *_ in (r + [""] for r in _parse(self.hook.send("dialogs")))}

    def _children(self, dlg: str) -> list[dict]:
        out = []
        for h, cls, cid, text, geo, flags in ((r + [""] * 6)[:6] for r in _parse(self.hook.send("children", dlg))):
            x, y, w, hh = (int(v) for v in geo.split()) if geo else (0, 0, 0, 0)
            out.append({"h": h, "cls": cls.lower(), "id": int(cid or 0), "text": text, "x": x, "y": y, "w": w, "h_": hh,
                        "visible": flags[:1] == "1", "enabled": flags[1:2] == "1"})
        return out

    def _dialog_report(self) -> str:
        """What MC9's dialogs say (e.g. 'Text .MODEL ... expected )'): the best clue when something did not start."""
        try:
            lines = []
            for h, title in self._dialogs().items():
                texts = [c["text"] for c in self._children(h) if c["cls"] == "static" and c["text"].strip()]
                lines.append(f"[{title}] " + " | ".join(texts))
            return ": " + "; ".join(lines) if lines else ""
        except Exception:
            return ""

    def _wait_new_dialog(self, before: set[str], timeout: float) -> str | None:
        end = time.time() + timeout
        while time.time() < end:
            new = [h for h in self._dialogs() if h not in before]
            if new:
                return new[-1]
            time.sleep(0.2)
        return None

    def _wait_closed(self, dlg: str, timeout: float) -> None:
        end = time.time() + timeout
        while time.time() < end and dlg in self._dialogs():
            time.sleep(0.2)

    # ---- Driver interface ---------------------------------------------------------------------
    def open_analysis(self, key: str) -> None:
        before = set(self._dialogs())
        self.cmd.post(key)
        dlg = self._wait_new_dialog(before, 25)
        self._dyn = dlg if key in ("dynamic_dc", "dynamic_ac") else None
        if dlg is None and self._dyn is None and key in ("dynamic_dc", "dynamic_ac"):
            raise TimeoutError("the Dynamic DC/AC dialog did not appear")
        time.sleep(0.5)

    def press_run(self) -> None:
        self.cmd.post("run")
        time.sleep(0.5)

    def confirm_dynamic(self, key: str) -> None:
        dlg = self._dyn or self._wait_new_dialog(set(), 10)
        kids = self._children(dlg)
        ok = next((c for c in kids if c["id"] == 1 and c["cls"] == "button"), None) \
            or next(c for c in kids if c["cls"] == "button" and c["visible"] and c["enabled"])
        self.hook.send("click", ok["h"])
        self._wait_closed(dlg, 60)
        self._dyn = None
        time.sleep(1.5)

    def set_cursors(self, left: str, right: str | None) -> None:
        before = set(self._dialogs())
        self.cmd.post("cursors")
        dlg = self._wait_new_dialog(before, 10)
        if dlg is None:
            raise TimeoutError("MC9's 'go to X' dialog did not appear")
        time.sleep(0.5)
        kids = self._children(dlg)
        edit = next(c for c in kids if c["cls"] == "edit" and c["visible"])
        buttons = sorted((c for c in kids if c["cls"] == "button" and c["visible"] and c["enabled"]), key=lambda c: c["x"])
        by_text = {c["text"].strip().lower(): c for c in buttons}
        b_left = by_text.get("left", buttons[0])
        b_right = by_text.get("right", buttons[1])
        b_close = by_text.get("close", buttons[2])
        self.hook.send("settext", f"{edit['h']} {left}")
        self.hook.send("click", b_left["h"])
        time.sleep(1)
        if right is not None:
            self.hook.send("settext", f"{edit['h']} {right}")
            self.hook.send("click", b_right["h"])
            time.sleep(1)
        self.hook.send("click", b_close["h"])
        self._wait_closed(dlg, 10)
        time.sleep(0.5)

    def exit_analysis(self) -> None:
        self.cmd.post("exit")
        time.sleep(2)

    def prepare_capture(self, schematic: bool) -> None:
        if schematic:
            self.cmd.post("select")                   # leave component-placement mode (the ghost symbol follows the pointer)
            self.hook.send("key", "escape")
        _, left, top, _, _ = self.hook.send("frame").split()
        self.hook.send("park", f"{int(left) + L.window[0] - 2} {int(top) + L.window[1] - 2}")   # no hover tracker / tooltip
        time.sleep(1)

    def grab(self):
        from PIL import Image
        if self.session is not None:
            f = workspace.exchange() / "_grab.png"
            self.session.cmd("shot _grab.png")
            img = Image.open(f).convert("RGB")
            img.load()
            f.unlink(missing_ok=True)
            return img
        from PIL import ImageGrab
        _, left, top, _, _ = self.hook.send("frame").split()
        left, top = int(left), int(top)
        return ImageGrab.grab(bbox=(left, top, left + L.window[0], top + L.window[1])).convert("RGB")
