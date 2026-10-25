"""Open MC9's Optimizer dialog (Ctrl+F11) on an RC filter and describe it."""

import sys
import time

import mc9

mc9.config.engine = "native"
c = mc9.library.rc_lowpass().build("opt_t")
c.ac(10, 1e5, 401, ["db(v(out))"])
d = c._session().d
h = d.hook
h.send("watch", "on all"); h.send("watch", "clear")
before = set(d._dialogs())
h.send("sendkey", sys.argv[1] if len(sys.argv) > 1 else "ctrl+F11")
time.sleep(4)
print("events", h.send("watch", "dump")[:200])
new = [x for x in d._dialogs() if x not in before]
print("new dialogs", {x: d._dialogs()[x] for x in new})
for dh in new:
    for k in d._children(dh):
        if k["cls"] != "richedit20a":
            print("  ", k["cls"], k["id"], repr(k["text"]), k["visible"], k["enabled"], (k["x"], k["y"], k["w"], k["h_"]))
d.session.cmd("shot explore_opt.png")
d.close()
