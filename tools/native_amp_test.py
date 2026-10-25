import mc9
from mc9 import audio

mc9.config.engine = "native"
s = audio.Specs(p_out=24, r_load=6, r_in=60e3, f_low=25, f_high=18e3, thd=0.3)
c = audio.schematic(s).build("ppzch", labels="dc")
c.set("V1", "VALUE", "DC 0 AC 1 0")
op = c.op()
print({k: round(v, 3) for k, v in op.nodes.items()})
for q in ("Q1", "Q2", "Q3", "Q4"):
    print(q, round(op[q]["IC"] * 1e3, 2), "mA")
print(c.shot("ppzch_dc.png", "schematic"))
c.close()
