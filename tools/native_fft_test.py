import mc9
from mc9 import library

mc9.config.engine = "native"
c = library.rc_lowpass().build("fft_t")
c.set("V1", "VALUE", "DC 0 AC 1 0 Sin 0 1 1k 0 0 0")
r = c.transient(10e-3, 0, points=1001, curves=["v(out)", ("F", "db(mag(fft(v(out))))")], max_step=2e-6)
print(r, [(x.columns, len(x)) for x in r.runs])
print(c.shot("fft_t.png"))
c.close()
