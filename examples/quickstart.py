"""README quickstart: describe an RC low-pass, let mc9 draw it, analyse it in MC9, save MC9's own pictures."""

from mc9 import Netlist, measure, sources

n = Netlist()
n.V("V1", "in", "0", sources.sine(0.1, 1e3))
n.R("R1", "in", "out", "1k")
n.C("C1", "out", "0", "159.155n")  # fc = 1 kHz

c = n.build("rc")  # place parts, route wires, write the circuit

print("operating point:", c.op().nodes)
r = c.ac(10, 1e5, 401, ["db(v(out))"])
bw = measure.bandwidth(c, "db(v(out))", cursors=True)  # -3 dB point, MC9 cursors placed on it
print(f"-3 dB at {bw.f_high:.1f} Hz (ideal 1000)")
print(c.shot("rc_ac.png"))  # MC9's own AC plot with its cursor table
c.dynamic_dc(25)
print(c.shot("rc_dc.png", "schematic"))  # schematic with node voltages
c.close()
