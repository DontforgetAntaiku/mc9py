"""Map MC9's menus: photograph a drop-down, or click an item and record its command id and the dialogs it opens.

usage: python tools/probe_menus.py shots
       python tools/probe_menus.py click <menu> <item> [<item> ...]      (items are 0-based; --state schematic|analysis|mc)
The session is an ordinary native-engine session; xdotool is used here only to find out what a menu item does.
"""
import sys
import time

import mc9

MENU_X = {"file": 38, "edit": 105, "comp": 188, "windows": 244, "options": 285, "analysis": 414, "scope": 590, "mc": 698, "help": 760}
FIRST, DY, BAR_Y = 57, 17, 41

args = [a for a in sys.argv[1:] if not a.startswith("--")]
state = next((a.split("=")[1] for a in sys.argv if a.startswith("--state=")), "mc")
mc9.config.engine = "native"
c = mc9.library.rc_lowpass().build("probe_menus")
if state == "mc":
    c.tolerance("R1", lot="10%")
    c.monte_carlo(runs=10, seed=1, analysis="transient")
    c.histogram("Y_Level(v(out),1,1,10m)")
if state in ("analysis", "mc"):
    c.transient(10e-3, 0, points=201, curves=["v(out)"])
d = c._session().d
h, s = d.hook, d.session


def open_menu(name):
    s.cmd(f"c {MENU_X[name]} {BAR_Y}")
    time.sleep(1)


mode = args[0] if args else "shots"
if mode == "shots":
    for name in MENU_X:
        open_menu(name)
        s.cmd(f"shot probe_{state}_{name}.png")
        s.cmd("k Escape")
        time.sleep(0.5)
else:
    menu = args[1]
    for item in map(int, args[2:]):
        h.send("watch", "on all"); h.send("watch", "clear")
        before = set(d._dialogs())
        open_menu(menu)
        s.cmd(f"c {MENU_X[menu] + 40} {FIRST + DY * item}")
        time.sleep(3)
        ev = [e for e in h.send("watch", "dump").split() if e.startswith("111:")][:3]
        new = {k: v for k, v in d._dialogs().items() if k not in before}
        print(f"{menu}[{item}] commands={[(int(e.split(':')[1], 16) & 0xFFFF, int(e.split(':')[1], 16) >> 16) for e in ev]} dialogs={new}")
        for dh in new:
            for k in d._children(dh):
                if k["cls"] not in ("richedit20a", "static") and k["id"] not in (0, 65535):
                    print("    ", k["cls"], k["id"], repr(k["text"]), k["visible"], k["enabled"])
        s.cmd(f"shot probe_{state}_{menu}_{item}.png")
        for dh in new:                                  # close what opened
            kids = d._children(dh)
            btn = next((k for k in kids if k["id"] in (2, 8, 23) and k["cls"] == "button"), None)
            if btn:
                h.send("click", btn["h"])
        s.cmd("k Escape")
        time.sleep(1)
c.close()
