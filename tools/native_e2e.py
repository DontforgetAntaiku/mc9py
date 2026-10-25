"""Whole workflow on the native engine (the default): no mouse or keyboard input is used."""

import mc9
from mc9 import library, measure

mc9.config.engine = "native"          # fail loudly instead of falling back to clicks
c = library.rc_lowpass().build("native_rc")
print("start")
print("OP", c.op().nodes)
r = c.ac(10, 1e5, 301, ["db(v(out))"])
bw = measure.bandwidth(c, "db(v(out))", cursors=True)       # cursor dialog through the DLL
print("AC gain@1k %.2f dB, f_high %.1f Hz" % (r.value_at("db(v(out))", 1000), bw.f_high))
print(c.shot("native_rc_ac.png"))
c.dynamic_dc(25)                                              # Dynamic DC dialog through the DLL
print(c.shot("native_rc_dc.png", "schematic"))
c.dynamic_ac(1000)
print(c.shot("native_rc_dac.png", "schematic"))
c.close()
