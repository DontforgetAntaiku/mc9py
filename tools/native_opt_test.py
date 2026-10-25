import mc9
from mc9 import library

mc9.config.engine = "native"
c = library.rc_lowpass().build("opt_t")        # R1 = 1k, C1 = 159.155n  -> fc = 1 kHz
# find R1 so that the -3 dB point lies at 2 kHz: gain at 2 kHz must be -3.0103 dB for fc = 2 kHz
res = c.optimize({"R1": (100, 5000)}, [("equals", "Y_Level(db(v(out)),1,1,2000)", -3.0103)], analysis="ac")
print(res)
print("R1 now", c.get("R1", "RESISTANCE"))
c.close()
