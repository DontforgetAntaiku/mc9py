"""Client for mc9hook.dll, the helper loaded into MC9 (see ``native/``). Requests are files in the exchange folder."""

from __future__ import annotations

import os
import time
import uuid

from . import workspace


class HookError(RuntimeError):
    pass


class Hook:
    """Talk to a running ``mc9hook.dll``: ``Hook().send("ping")`` -> ``"pong"``."""

    def __init__(self, directory: str | None = None):
        self.dir = directory or workspace.exchange()

    def send(self, command: str, args: str = "", timeout: float = 15.0) -> str:
        req, tmp, resp = (os.path.join(self.dir, n) for n in ("hook.req", "hook.req.tmp", "hook.resp"))
        if os.path.exists(resp):
            os.remove(resp)
        rid = uuid.uuid4().hex[:8]
        with open(tmp, "w") as f:
            f.write(f"{rid} {command} {args}".strip())
        os.replace(tmp, req)
        end = time.time() + timeout
        while time.time() < end:
            if os.path.exists(resp):
                try:
                    text = open(resp).read().strip()
                except OSError:
                    continue
                os.remove(resp)
                got, status, body = (text + "  ").split(" ", 2)
                if got == rid:
                    if status != "ok":
                        raise HookError(body.strip())
                    return body.strip()
            time.sleep(0.02)
        raise HookError(f"no answer to '{command}' (is MC9 running with mc9hook.dll?)")


_FILES = ("mc9hook.dll", "mc9launch.exe", "signatures.txt")


def native_dir():
    """Where the built hook lives: ``native/`` in a source checkout, ``mc9/_native`` in an installed package."""
    from pathlib import Path

    here = Path(__file__).resolve().parent
    for d in (here / "_native", here.parents[1] / "native"):
        if (d / "mc9hook.dll").exists():
            return d
    raise HookError("mc9hook.dll is not built: run `make -C native` (needs i686-w64-mingw32-gcc)")


def install(dest=None):
    """Copy the hook files next to the circuits so MC9 (and Wine) can reach them; returns the folder."""
    import shutil

    src, dest = native_dir(), dest or workspace.exchange()
    for name in _FILES:
        if (src / name).exists():
            shutil.copy2(src / name, dest / name)
    return dest


# Keyboard accelerators of MC9 (the same in every language) -> the command each one is bound to.
ACCELERATORS = {"transient": "alt+1", "ac": "alt+2", "dc": "alt+3", "dynamic_dc": "alt+4", "dynamic_ac": "alt+5",
                "distortion": "alt+8", "run": "F2", "exit": "F3"}


class Native:
    """Commands that MC9 understands without any keyboard or mouse: ``native.invoke("transient")``.

    MC9 numbers its commands per build. The first time a command is needed its accelerator is pressed once and the
    number is read from the WM_COMMAND the window receives; it is then remembered (``settings.json``, keyed by the
    fingerprint of the MC9 build) and posted directly from then on. ``press(key)`` must send one key to MC9.
    """

    def __init__(self, press, hook: Hook | None = None):
        self.hook, self.press = hook or Hook(), press
        info = dict(kv.split("=", 1) for kv in self.hook.send("info").split() if "=" in kv)
        self.fingerprint = info.get("fp", "unknown")
        self.ids: dict[str, int] = dict(workspace.settings().get("native_ids", {}).get(self.fingerprint, {}))

    def _remember(self) -> None:
        known = workspace.settings().get("native_ids", {})
        known[self.fingerprint] = self.ids
        workspace.save_settings(native_ids=known)

    def learn(self, kind: str, timeout: float = 6.0) -> int | None:
        """Press the accelerator of ``kind`` and read the command id MC9 receives."""
        self.hook.send("watch", "on")
        try:
            end = time.time() + timeout
            self.press(ACCELERATORS[kind])
            while time.time() < end:
                for ev in self.hook.send("watch", "dump").split():
                    msg, wparam, _, _ = ev.split(":")
                    if int(msg, 16) == 0x111:                      # WM_COMMAND to the main window
                        self.ids[kind] = int(wparam, 16) & 0xFFFF
                        self._remember()
                        return self.ids[kind]
                time.sleep(0.2)
        finally:
            self.hook.send("watch", "off")
        return None

    def invoke(self, kind: str) -> bool:
        """Do what the accelerator of ``kind`` does. The first call also performs it (by key) while learning the id."""
        if kind in self.ids:
            self.hook.send("post_cmd", str(self.ids[kind]))
            return True
        return self.learn(kind) is not None
