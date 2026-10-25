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
