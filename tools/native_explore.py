"""Poke at MC9's other analyses: Alt+6 / Alt+7 and the Monte Carlo menu."""

import sys
import time

import mc9

mc9.config.engine = "native"
c = mc9.library.rc_lowpass().build("explore")
d = c._session().d
h = d.hook
for key in sys.argv[1:] or ["alt+6", "alt+7"]:
    h.send("watch", "on all"); h.send("watch", "clear")
    h.send("sendkey", key)
    time.sleep(4)
    ev = [e for e in h.send("watch", "dump").split() if e.startswith("111:")][:2]
    print("==", key, ev)
    for dh, title in d._dialogs().items():
        print("  dialog", dh, title)
        for k in d._children(dh):
            if k["cls"] not in ("richedit20a",) and k["id"] != 65535:
                print("     ", k["cls"], k["id"], repr(k["text"]), k["visible"], k["enabled"])
    d.session.cmd(f"shot explore_{key.replace('+', '_')}.png")
    h.send("watch", "off")
    h.send("sendkey", "escape"); time.sleep(1)
    h.send("sendkey", "F3"); time.sleep(2)
d.close()
