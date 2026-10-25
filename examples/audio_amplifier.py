"""Audio power amplifier coursework: starter circuit, bias tuning and the whole set of measurements (needs MC9; about 30 minutes)."""

import mc9
from mc9 import audio

# the row of your table: P_out [W], R_load [ohm], R_in [ohm], f_low [Hz], f_high [Hz], THD [%]
specs = audio.Specs(p_out=24, r_load=6, r_in=60e3, f_low=25, f_high=18e3, thd=0.3)
print(specs.summary())                                  # amplitude, current, gain, supply voltage, class-B efficiency ...

c = audio.schematic(specs).build("amp", labels="dc")    # MC9's own schematic file, ready to open in MC9
bench = audio.Bench(c, specs)
bench.tune_quiescent(0.05)                              # bias the output pair to 50 mA each
results = audio.report(bench)                           # AC/phase, sines at f_low/f0/f_high at 0/25/70 degC, clipping, squares,
print(audio.format_report(results, specs))              # THD at 1 and 10 kHz, max power, slew, Rout, supply current, efficiency ...
c.close()
