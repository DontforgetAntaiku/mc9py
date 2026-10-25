import sys
sys.path.insert(0, "tests")
import mc9
from mc9 import Netlist, sources

mc9.config.engine = "native"
n = Netlist()
n.V("V1", "in", "0", sources.sine(0.1, 1e3))
n.C("C1", "in", "g", "1u")
n.R("RG", "g", "0", "1Meg")
n.J("J1", "d", "g", "s", "J111")
n.R("RD", "vdd", "d", "4.7k")
n.R("RS", "s", "0", "1k")
n.C("C2", "d", "out", "1u")
n.R("RL", "out", "0", "100k")
n.VB("V2", "vdd", "0", "12")
c = n.build("jfet_stage", labels="ac")
op = c.op()
print({k: round(v, 3) for k, v in op.nodes.items()})
print("ID", op["J1"])
r = c.ac(10, 1e6, 401, ["db(v(out)/v(in))"])
print("gain @1k: %.2f dB" % r.value_at("db(v(out)/v(in))", 1000))
c.dynamic_ac(1000)
print(c.shot("jfet_stage_ac.png", "schematic"))
c.close()
