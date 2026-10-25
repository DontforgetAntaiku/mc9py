"""Inverting op-amp stage (gain -10) generated from Python: checks the op-amp pin geometry end to end."""

import mc9
from mc9 import sources

s = mc9.Schematic()
v1 = s.add("V", "V1", sources.sine(0.1, 1e3), at=(0, 22), rot=3)
gv = s.add("GND", None, at=(0, 22))  # ground hangs below V1.Minus
r1 = s.add("R", "R1", "10k", at=(6, 16))
u1 = s.add("OPAMP", "U1", "LM741", at=(30, 10))  # pins: 'Plus input','Minus input','VEE','Output','VCC'
rf = s.add("R", "Rf", "100k", at=(24, -4))
rl = s.add("R", "RL", "10k", at=(44, 13), rot=1)
gp = s.add("GND", None, at=(26, 10))  # + input to ground
gl = s.add("GND", None, at=(44, 19))
vcc = s.add("VB", "V2", "15", at=(34, 2), rot=1)  # rot 1: Minus on top, Plus below -> VCC pin
gcc = s.add("GND", None, at=(34, 2), rot=3)  # symbol points up, away from the opamp
vee = s.add("VB", "V3", "15", at=(34, 18), rot=1)  # Minus on top -> VEE pin, Plus -> ground
gee = s.add("GND", None, at=(34, 24))
W = s.wire
W(v1.Plus, r1.Minus)
W(r1.Plus, u1.pin("Minus input"))
W(u1.pin("Plus input"), gp.PinA)
W((22, 16), (22, -4))
W((22, -4), rf.Minus)
W(rf.Plus, (44, -4))
W((44, -4), (44, 13))
W((44, 13), u1.Output)
W(rl.Plus, gl.PinA)
W(vcc.Plus, u1.VCC)
W(vee.Minus, u1.VEE)
W(vee.Plus, gee.PinA)
s.node("Vin", (3, 16))  # on the wire, clear of R1's body
s.node("Vout", u1.Output)
s.node("Vout", u1.Output)
c = s.build("inv_amp", labels="dc", chars=7)
print("notes/issues printed above if any; zoom", s.zoom)
op = c.op()
print({k: round(v, 3) for k, v in op.nodes.items()})
r = c.ac(10, 1e6, 401, ["db(v(Vout)/v(Vin))"])
print("gain @1kHz: %.2f dB (ideal 20.0)" % r.value_at("db(v(Vout)/v(Vin))", 1000))
c.dynamic_dc(25)
print(c.shot("inv_amp_dc.png", "schematic"))
c.close()
