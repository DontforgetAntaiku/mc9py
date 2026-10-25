"""Find out which WM_COMMAND ids MC9's accelerators send: start MC9 with the hook, press keys, read the log."""

import sys
import time

import mc9
from mc9 import native
from mc9.backends.linux_wine import Session

mc9.config.native = True
name = "watch_demo"
c = mc9.library.rc_lowpass().build(name)
c.close()
s = Session(name)
h = native.Hook()
print("info", h.send("info"))
print("windows", h.send("windows"))
print("watch", h.send("watch", "on"))
def first_frame_cmd(dump):
    """First WM_COMMAND sent to the main window (the first event of the dump)."""
    ev = dump.split()[0].split(":") if dump else None
    return int(ev[1], 16) & 0xFFFF if ev else None


for label, key in (("transient", "alt+1"), ("run", "F2"), ("exit", "F3"), ("dynamic_dc", "alt+4"), ("dynamic_ac", "alt+5"), ("exit", "F3")):
    h.send("watch", "clear")
    s.cmd(f"k {key}")
    time.sleep(8 if label == "run" else 3)
    d = h.send("watch", "dump")
    print(label, key, first_frame_cmd(d), d[:160])
    sys.stdout.flush()
print("--- no keys: post_cmd 83158 (transient) ---")
h.send("watch", "clear")
print(h.send("post_cmd", "83158"))
time.sleep(4)
print(h.send("watch", "dump")[:120])
s.cmd("shot posted.png")
s.close()
