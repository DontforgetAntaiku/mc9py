import json
import sys

import mc9
from mc9 import audio

mc9.config.engine = "native"
s = audio.Specs(p_out=24, r_load=6, r_in=60e3, f_low=25, f_high=18e3, thd=0.3)
c = audio.schematic(s).build("ppzch", labels="dc")
b = audio.Bench(c, s)
print("tuned RUP/RDN =", b.tune_quiescent(0.05))
quick = "--full" not in sys.argv
r = audio.report(b, quick=quick)
print(audio.format_report(r, s))
json.dump(r, open("sandbox/exchange/ppzch_report.json", "w"), indent=1, default=str)
c.close()
