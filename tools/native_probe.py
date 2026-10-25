"""Talks to mc9hook.dll inside a running MC9 and checks the offset auto-search against the build the signatures came from."""

from mc9.native import Hook

h = Hook()
assert h.send("ping") == "pong"
print("info   ", h.send("info"))
for mode in ("", "anchor"):                        # byte patterns first, then only the string anchors
    out = h.send("resolve", mode)
    print("resolve %-7s" % (mode or "pattern"), out)
    assert "MOVED" not in out and "(none" not in out, out
print("msgmap  ", h.send("msgmap", "1"))           # MFC message-map handlers of command id 1
print("OK: every target found at run time by both methods")
