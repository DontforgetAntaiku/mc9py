"""Whole workflow with config.native = True: analyses are started by posted commands, not by menu clicks."""

import mc9
from mc9 import library, measure

mc9.config.native = True
c = library.rc_lowpass().build("native_rc")
print("OP", c.op().nodes)
r = c.ac(10, 1e5, 301, ["db(v(out))"])
bw = measure.bandwidth(c, "db(v(out))", cursors=True)
print("AC gain@1k %.2f dB, f_high %.1f Hz" % (r.value_at("db(v(out))", 1000), bw.f_high))
print(c.shot("native_rc_ac.png"))
c.dynamic_dc(25)
print(c.shot("native_rc_dc.png", "schematic"))
print("ids", c._ui.d.nat.ids)
c.close()
