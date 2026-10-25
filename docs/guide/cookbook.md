# Lab cookbook

Typical tasks of an analog-electronics lab as short recipes. They use the starter amplifier from `mc9.library`
(a common-emitter stage, BF420, 18 V); replace it with `mc9.open("your_lab.cir")` for your own circuit.

```python
import mc9
from mc9 import library, measure, sources

c = library.ce_amplifier().build("amp", labels="ac")      # nodes: src, ue, b, col, ua, vcc
```

## Operating point and what it says

```python
op = c.op()
q = op["Q1"]
print(f"VB = {q['VBE']:.4f} V   VC = {q['VCE']:.3f} V   IC = {q['IC']*1e3:.3f} mA   IB = {q['IB']*1e6:.1f} uA   hFE = {q['BETADC']:.1f}")
print(f"gm = {q['GM']*1e3:.1f} mS   rpi = {q['RPI']:.0f} ohm   ro = {q['RO']/1e3:.2f} kohm   P(R3) = {op['R3']['PD']*1e3:.1f} mW")

c.dynamic_dc(25)
c.shot("bias.png", "schematic")           # the node voltages as MC9 draws them
```

## Temperature and supply stability of the bias point

```python
for t in (0, 25, 50):
    c.limits("transient", Temp=t)
    print(t, "C   VC =", round(c.op()["Q1"]["VCE"], 3), "V")
c.limits("transient", Temp=25)

for vcc in (14.4, 18, 21.6):               # supply -20 % / nominal / +20 %
    c.set("V2", "VALUE", vcc)
    print(vcc, "V   VC =", round(c.op()["Q1"]["VCE"], 3), "V")
c.set("V2", "VALUE", 18)
```

## Frequency response, gain and band edges

```python
bw = measure.bandwidth(c, "db(v(ua)/v(ue))", cursors=True)       # puts MC9's cursors on the -3 dB points
print(f"G0 = {bw.g0_db:.2f} dB at {bw.f0:.0f} Hz;  band {bw.f_low:.1f} Hz .. {bw.f_high/1e3:.2f} kHz")
c.shot("gain.png")                                                # MC9's own plot with its cursor table

r = c.ac(1, 2e7, 801, ["ph(v(ua)/v(ue))"])
f180 = r.cross("ph(v(ua)/v(ue))", -180)[0]                        # frequency where the phase passes -180 degrees
```

!!! note
    Band edges are read from a **log** sweep (`c.ac`/`measure.bandwidth` always use one). MC9's default `Auto` sweep gives a coarse
    table and cursors interpolate between points - the edges can be wrong by 10 % or more.

## Input and output resistance

```python
rin = measure.rin(c, "v(ue)", "i(R1)", 2224)                       # |v(ue) / i(R1)| at 2.224 kHz
rout = measure.rout(c, "v(ua)", load="R4", f=2224)                 # load removal: R4 -> 1T temporarily
print(f"Rin = {rin:.0f} ohm, Rout = {rout:.0f} ohm")
```

## Non-linear distortion at several amplitudes

```python
rows = []
for amp in (35e-3, 10.5e-3, 3.5e-3):
    d = measure.thd(c, 2224, "V1", amp, "v(ua)")
    rows.append((amp * 1e3, d["h"][1], d["k_pct"][2], d["thd_pct"]))
print("amp, mV | Ua(1), V | K2, % | THD, %")
for row in rows:
    print("%8.1f | %8.3f | %5.2f | %6.2f" % row)

c.distortion(2224, "V1", 35e-3, "v(ua)")      # MC9's own HARM / IHD / THD window for the report
c.shot("distortion.png")
```

## Largest undistorted amplitude

```python
lo, hi = 1e-3, 100e-3                          # source amplitude, V
for _ in range(7):                             # bisection on THD = 5 %
    mid = (lo * hi) ** 0.5
    thd = measure.thd(c, 2224, "V1", mid, "v(ua)")["thd_pct"]
    lo, hi = (mid, hi) if thd < 5 else (lo, mid)
print(f"~{lo*1e3:.1f} mV at the source")
```

## Square-wave response

```python
c.set("V1", "VALUE", sources.pulse(-10.5e-3, 10.5e-3, 449.6e-6))          # +-10.5 mV square wave, period 449.6 us
c.transient(40e-3, 35e-3, points=2001, curves=["v(ue)", "v(ua)"])
c.shot("square.png")                           # sag of the flat top = low cut-off, rounded edges = high cut-off
```

## Find a component value

```python
# R2 for a collector potential of 9.5 V (each step is one MC9 start, ~25 s)
r2 = measure.solve(c, "R2", "RESISTANCE", lambda op: op["Q1"]["VCE"], target=9.5, lo=100e3, hi=500e3)
print(f"R2 = {r2/1e3:.1f} kohm")
```

## "Calculation vs simulation" table

```python
calc = {"VC, V": 9.5, "IC, mA": 7.08, "Rin, ohm": 182, "Rout, ohm": 1113}
sim = {"VC, V": q["VCE"], "IC, mA": q["IC"] * 1e3, "Rin, ohm": rin, "Rout, ohm": rout}
print("| parameter | calculation | simulation | error, % |\n|---|---|---|---|")
for k, v in calc.items():
    print(f"| {k} | {v:g} | {sim[k]:.4g} | {100 * (sim[k] - v) / v:+.1f} |")
```

## Several pictures for a report

Every `c.shot(...)` writes a PNG into `mc9.exchange_dir()`; names are yours. A typical report needs: the schematic
(`"schematic"`), the schematic with voltages (`c.dynamic_dc()`), the AC plot with cursors, a transient plot, the distortion window.

!!! tip
    Close MC9 when you are done: `c.close()` (or use `with mc9.open(...) as c:`), otherwise it keeps running in the background.
