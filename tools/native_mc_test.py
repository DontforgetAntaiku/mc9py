import sys

import mc9
from mc9 import library

mc9.config.engine = sys.argv[1] if len(sys.argv) > 1 else "native"
c = library.rc_lowpass().build("mc_t")
c.tolerance("R1", lot="10%")
c.monte_carlo(runs=5, seed=1, analysis="transient")
r = c.transient(5e-3, 0, points=101, curves=["v(out)"])
print(r, [x.label for x in r.runs])
print([round(x["v(out)"][50], 4) for x in r.runs])
print(c.shot("mc_t.png"))
c.close()
