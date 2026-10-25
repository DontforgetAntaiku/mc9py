import sys

import mc9
from mc9 import library

mc9.config.engine = sys.argv[1] if len(sys.argv) > 1 else "native"
c = library.ce_amplifier().build("temp_t", labels="dc")
r = c.dc("V2", 0, 20, 2, curves=["v(col)"], temp=[0, 25, 75])
print(r, [x.params for x in r.runs])
print([round(x["v(col)"][-1], 3) for x in r.runs])
op = c.op()
print(op["Q1"]["IC"])
c.close()
