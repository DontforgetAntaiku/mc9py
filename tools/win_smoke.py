"""Runs on *Windows Python* (also Wine): exercises the Windows backend end to end."""

import time
import warnings

warnings.simplefilter("ignore")
import mc9
from mc9 import sources

mc9.config.backend = "windows"
s = mc9.Schematic()
v = s.add("V", "V1", sources.sine(0.1, 1e3), at=(0, 8), rot=3)
r = s.add("R", "R1", "1k", at=(10, 2))
c_ = s.add("C", "C1", "159.155n", at=(26, 2), rot=1)
g = s.add("GND", None, at=(26, 14))
s.wire(v.Plus, r.Minus)
s.wire(r.Plus, c_.Minus)
s.wire(c_.Plus, g.PinA)
s.wire(v.Minus, (0, 14))
s.wire((0, 14), g.PinA)
s.node("Out", (18, 2))
c = s.build("win_rc", labels="dc")
t0 = time.time()
try:
    op = c.op()
    print("OP", op.nodes, round(time.time() - t0), "s", flush=True)
    r_ = c.ac(10, 1e5, 401, ["db(v(Out))"])
    print("AC rows", len(r_), "gain@1k %.2f dB" % r_.value_at("db(v(Out))", 1000), flush=True)
    c.cursors(1000, 2000)
    print("cursors ok", flush=True)
    print(c.shot("win_rc_ac.png"), flush=True)
    c.dynamic_dc(25)
    print(c.shot("win_rc_dc.png", "schematic"), flush=True)
finally:
    c.close()
print("DONE", flush=True)
