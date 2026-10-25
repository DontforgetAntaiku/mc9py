"""Monte Carlo histogram tab, statistics window and options dialog: find their controls and command ids."""
import time

import mc9

mc9.config.engine = "native"
c = mc9.library.rc_lowpass().build("probe_mc")
c.tolerance("R1", lot="10%")
c.tolerance("C1", lot="5%")
c.monte_carlo(runs=25, seed=1, analysis="transient")
c.histogram("Y_Level(v(out),1,1,10m)")
c.transient(10e-3, 0, points=201, curves=["v(out)"])
d = c._session().d
h, s = d.hook, d.session
import re
wins = h.send("mdi")
print("mdi:", wins)
found = re.findall(r"\[([0-9A-F]+) (\S+) \"([^\"]*)\" (\d+x\d+)", wins)
h.send("watch", "on all")
for hw, _cls, title, _size in found:
    if "Y_Level" in title or "Level" in title:
        h.send("mdi", hw)
        time.sleep(2)
        s.cmd("shot probe_mc_hist_tab.png")
for label, y in (("options", 57), ("histogram", 74), ("statistics", 91)):
    h.send("watch", "clear")
    before = set(d._dialogs())
    s.cmd("c 698 41"); time.sleep(1)
    s.cmd(f"c 738 {y}"); time.sleep(3)
    ev = [e for e in h.send("watch", "dump").split() if e.startswith("111:")][:3]
    new = {k: v for k, v in d._dialogs().items() if k not in before}
    print(label, [(int(e.split(":")[1], 16) & 0xFFFF) for e in ev], new)
    for dh in new:
        for k in d._children(dh):
            if k["cls"] not in ("richedit20a", "static") and k["id"] not in (0, 65535):
                print("    ", k["cls"], k["id"], repr(k["text"]), k["visible"], k["enabled"])
    s.cmd(f"shot probe_mc_{label}.png")
    for dh in new:
        btn = next((k for k in d._children(dh) if k["id"] in (2, 8, 23) and k["cls"] == "button"), None)
        if btn:
            h.send("click", btn["h"])
    s.cmd("k Escape"); time.sleep(1)
h.send("watch", "clear")
h.send("sendkey", "F6"); time.sleep(2)
print("F6", [(int(e.split(":")[1], 16) & 0xFFFF) for e in h.send("watch", "dump").split() if e.startswith("111:")][:3])
c.close()
