"""Rebuild the LR2 common-emitter stage from scratch with the Schematic builder, then verify it in MC9."""

import mc9

s = mc9.Schematic()
# columns are spaced so MC9's wide phasor boxes (Dynamic AC) do not collide
v1 = s.add("V", "V1", "DC 0 AC 3.5m 0 Sin 0 3.5m 2.224k 0 0 0", at=(0, 16), rot=3)
r1 = s.add("R", "R1", "200", at=(8, 10))
c1 = s.add("C", "C1", "3.47u", at=(30, 10))
q1 = s.add("Q", "Q1", at=(46, 10), MODEL="BF420")
r2 = s.add("R", "R2", "233.2k", at=(40, 0), rot=1)
r3 = s.add("R", "R3", "1.2k", at=(49, 0), rot=1)
c2 = s.add("C", "C2", "12n", at=(59, 7), rot=1)
c3 = s.add("C", "C3", "553n", at=(66, 7))
r4 = s.add("R", "R4", "1.2k", at=(92, 7), rot=1)
v2 = s.add("VB", "V2", "18", at=(100, 6), rot=3)
gnd = s.add("GND", None, at=(100, 17))
W = s.wire
W(v1.Plus, r1.Minus)
W(r1.Plus, c1.Minus)
W(c1.Plus, q1.Base)
W(r2.Plus, (40, 10))
W(r2.Minus, r3.Minus)
W(r3.Minus, v2.Plus)
W(r3.Plus, q1.Collector)
W(q1.Collector, c2.Minus)
W(c2.Minus, c3.Minus)
W(c3.Plus, r4.Minus)
W(v1.Minus, (0, 17))
W((0, 17), gnd.PinA)
W(q1.Emitter, (49, 17))
W(c2.Plus, (59, 17))
W(r4.Plus, (92, 17))
W(v2.Minus, gnd.PinA)
s.node("Ue", r1.Plus)
s.node("Ua", c3.Plus)

c = s.build("ce_amp", labels="ac")  # warns about any predicted collision / connectivity problem
print("zoom", s.zoom, "| audit dc:", s.audit("dc"), "| audit ac:", s.audit("ac"))
op = c.op()
print(
    "VB=%.4f V  VCE=%.3f V  IC=%.3f mA  beta=%.1f" % (op["Q1"]["VBE"], op["Q1"]["VCE"], op["Q1"]["IC"] * 1e3, op["Q1"]["BETADC"])
)
c.dynamic_dc(25)
print(c.shot("ce_amp_dc.png", "schematic"))
c.dynamic_ac(2224)
print(c.shot("ce_amp_ac.png", "schematic"))
c.close()
