import sys

import mc9
from mc9 import library

mc9.config.engine = sys.argv[1] if len(sys.argv) > 1 else "native"
c = library.rc_lowpass().build("step_t")
c.step("R1", "1k", "3k", "1k")
c.step("C1", "100n,159.155n")
r = c.transient(10e-3, 0, points=201, curves=["v(out)"])
print(r, [run.params for run in r.runs])
c.clear_steps()
r2 = c.ac(10, 1e5, 401, ["db(v(out))"])
print(r2)
c.step("R1", 100, 100000, 10, method="log", analysis="ac")
r3 = c.ac(10, 1e5, 401, ["db(v(out))"])
print(r3, [round(run.params["R1"]) for run in r3.runs])
c.close()
