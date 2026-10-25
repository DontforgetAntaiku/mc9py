# Measurements

`mc9.measure` contains the measurements that every analog lab asks for. Each helper runs the MC9 analyses it needs.

```python
from mc9 import measure
```

| Helper | Returns |
|---|---|
| `measure.bandwidth(c, "db(v(out)/v(in))", cursors=True)` | `Bandwidth(g0_db, f0, f_low, f_high)`; `f_low` / `f_high` are `None` for high-pass / low-pass. Optionally puts MC9's cursors on the edges. |
| `measure.gain_at(c, "v(out)", "v(in)", 1e3)` | `{'mag', 'db', 'phase_deg'}` at one frequency |
| `measure.rin(c, "v(Ue)", "i(R1)", 2224)` | input resistance \|v/i\| at a frequency |
| `measure.rout(c, "v(Ua)", load="R4", f=2224)` | output resistance by load removal (the load gets `1T` temporarily and is restored) |
| `measure.thd(c, 2224, "V1", 35e-3, "v(Ua)")` | harmonic amplitudes, `k_pct` per harmonic, and `thd_pct` from a steady-state DFT |
| `measure.solve(c, "R2", "RESISTANCE", lambda op: op["Q1"]["VCE"], target=9.5, lo=1e5, hi=1e6)` | the part value that hits a target (bisection on the operating point; each step costs one MC9 start, about 25 s) |

```python
bw = measure.bandwidth(c, "db(v(Ua)/v(Ue))")
print(f"G0 = {bw.g0_db:.2f} dB, {bw.f_low:.1f} Hz .. {bw.f_high/1e3:.2f} kHz")

d = measure.thd(c, 2224, "V1", 35e-3, "v(Ua)")
print({k: round(v, 2) for k, v in d["k_pct"].items() if k <= 4}, d["thd_pct"])
```

## Why THD is computed in Python

MC9's Distortion analysis shows correct plots but its *numeric* table is a corrupted FFT buffer under Wine, so
`measure.thd` simulates a steady-state transient and takes a DFT over whole periods on an exact time grid. Use
`c.distortion(...)` plus `c.shot(...)` when you need MC9's own HARM / IHD / THD figure.

## Your own measurements

Everything is plain Python on `Result` objects:

```python
r = c.transient(5e-3, 4e-3, points=2001, curves=["v(Ua)"])
gain = r.amplitude("v(Ua)") / 0.0035
```
