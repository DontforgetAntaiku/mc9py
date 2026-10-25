"""The native engine's link to MC9: ``mc9hook.dll`` runs inside MC9 and answers small requests (see ``native/``).

Requests are files in the exchange folder, so the same code works on Linux (MC9 under Wine) and on Windows.
"""

from __future__ import annotations

import os
import shutil
import time
import uuid
from pathlib import Path

from . import workspace


class HookError(RuntimeError):
    pass


class Hook:
    """Talk to a running ``mc9hook.dll``: ``Hook().send("ping")`` -> ``"pong"``."""

    def __init__(self, directory: str | os.PathLike | None = None):
        self.dir = str(directory or workspace.exchange())

    def send(self, command: str, args: str = "", timeout: float = 15.0) -> str:
        req, tmp, resp = (os.path.join(self.dir, n) for n in ("hook.req", "hook.req.tmp", "hook.resp"))
        if os.path.exists(resp):
            os.remove(resp)
        rid = uuid.uuid4().hex[:8]
        with open(tmp, "w", encoding="cp1251", errors="replace") as f:
            f.write(f"{rid} {command} {args}".strip())
        os.replace(tmp, req)
        end = time.time() + timeout
        while time.time() < end:
            if os.path.exists(resp):
                try:
                    with open(resp, encoding="cp1251", errors="replace") as f:
                        text = f.read().rstrip("\n")
                    os.remove(resp)
                except OSError:
                    continue
                got, status, body = (text + "  ").split(" ", 2)
                if got == rid:
                    if status != "ok":
                        raise HookError(body.strip())
                    return body.strip()
            time.sleep(0.02)
        raise HookError(f"no answer to '{command}' (is MC9 running with mc9hook.dll?)")

    def wait(self, timeout: float) -> None:
        """Wait until the DLL answers (MC9 has started and unpacked itself)."""
        end = time.time() + timeout
        while True:
            try:
                if self.send("ping", timeout=2) == "pong":
                    return
            except HookError:
                if time.time() > end:
                    raise HookError("mc9hook.dll did not answer: is it built/installed and is MC9 running?") from None


_FILES = ("mc9hook.dll", "mc9launch.exe", "signatures.txt")


def native_dir() -> Path:
    """Where the hook files are: ``mc9/_native`` in an installed package, ``native/`` in a source checkout."""
    here = Path(__file__).resolve().parent
    for d in (here / "_native", here.parents[1] / "native"):
        if (d / "mc9hook.dll").exists():
            return d
    raise HookError("mc9hook.dll is not available: install a release of mc9py, or build it with `make -C native`")


def install(dest: str | os.PathLike | None = None) -> Path:
    """Copy the hook files next to the circuits so MC9 (and Wine) can reach them; returns the folder."""
    src, dest = native_dir(), Path(dest or workspace.exchange())
    for name in _FILES:
        if (src / name).exists():
            shutil.copy2(src / name, dest / name)
    return dest


# Command ids of the MC9 build the library was calibrated on (fingerprint of its unpacked code -> {command: id}).
# For another build they are learned once by pressing the accelerators (`Commands.calibrate`) and kept in settings.json.
KNOWN_IDS = {
    "f9a291ea": {"transient": 17622, "ac": 17623, "dc": 17624, "dynamic_dc": 17629, "dynamic_ac": 17628, "distortion": 17630,
                 "run": 16068, "exit": 17152, "cursors": 17184, "select": 17561, "optimize": 18899, "save": 57603,
                 # plot-window (Scope) menu, found by clicking the menu items while the hook recorded the commands
                 "autoscale_visible": 17178, "restore_scale": 17632, "norm_y_min": 17269, "norm_y_max": 17270,
                 "goto_y": 17185, "goto_performance": 17191, "goto_case": 17195, "separate_window": 24101, "fill_scatter": 17176,
                 "plot_labels_times": 40021, "animation_options": 17181,
                 # analysis menu
                 "limits": 16071, "stepping": 18100, "watch": 17180, "breakpoints": 17182, "op_methods": 3371,
                 "numeric_output": 17150, "initial_conditions": 5400, "reduce_points": 18699},
}
ACCELERATORS = {"transient": "alt+1", "ac": "alt+2", "dc": "alt+3", "dynamic_dc": "alt+4", "dynamic_ac": "alt+5",
                "distortion": "alt+8", "run": "F2", "exit": "F3", "cursors": "ctrl+shift+x", "optimize": "ctrl+F11", "save": "ctrl+s"}


class Commands:
    """MC9's commands by name: ``Commands(hook).post("transient")`` does what Alt+1 does, with no input device involved."""

    def __init__(self, hook: Hook):
        self.hook = hook
        info = dict(kv.split("=", 1) for kv in hook.send("info").split() if "=" in kv)
        self.fingerprint = info.get("fp", "0x?").removeprefix("0x").lower()
        self.ids: dict[str, int] = dict(KNOWN_IDS.get(self.fingerprint, {}))
        self.ids.update(workspace.settings().get("native_ids", {}).get(self.fingerprint, {}))

    def calibrate(self, kind: str, timeout: float = 8.0) -> int:
        """Press the accelerator of ``kind`` once inside MC9 and read the command id it sends (needed once per MC9 build)."""
        self.hook.send("watch", "on all")
        try:
            self.hook.send("sendkey", ACCELERATORS[kind])
            end = time.time() + timeout
            while time.time() < end:
                for ev in self.hook.send("watch", "dump").split():
                    msg, wparam, _, _ = ev.split(":")
                    if int(msg, 16) == 0x111 and int(wparam, 16) >> 16 == 1:       # an accelerator
                        self.ids[kind] = int(wparam, 16) & 0xFFFF
                        known = workspace.settings().get("native_ids", {})
                        known.setdefault(self.fingerprint, {})[kind] = self.ids[kind]
                        workspace.save_settings(native_ids=known)
                        return self.ids[kind]
                time.sleep(0.2)
        finally:
            self.hook.send("watch", "off")
        raise HookError(f"could not learn the command for '{kind}'")

    def post(self, kind: str) -> None:
        if kind not in self.ids and kind not in ACCELERATORS:
            return                               # a command that has no accelerator and is unknown for this build: skip
        if kind not in self.ids:
            self.calibrate(kind)                 # this also performs the command once
            return
        self.hook.send("post_cmd", str(self.ids[kind]))
