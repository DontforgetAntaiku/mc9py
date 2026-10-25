# Analyses

All analyses return numbers parsed from MC9's own numeric output **and** leave MC9's plot window open, so you can follow
with [cursors and screenshots](screenshots.md).

| Call | What it does |
|---|---|
| `c.op()` | DC operating point: node voltages and per-device values (`IC`, `VBE`, `GM`, `RPI`, power ...). Fast, no waveform run. |
| `c.ac(fmin, fmax, points=401, curves=[...])` | Small-signal AC sweep. **Always logarithmic** (see the gotcha below). |
| `c.transient(t_stop, t_start=0, points=1001, curves=[...], max_step=None)` | Time domain. The result table has `points` rows between `t_start` and `t_stop`, so use `t_start > 0` to look at steady state. |
| `c.dc(source, start, stop, step, curves=[...], temp=[0, 25, 50])` | DC sweep of a source or part; a temperature list gives one run per temperature. |
| `c.distortion(f0, source, amplitude, out)` | MC9's Distortion window (HARM / IHD / THD plots), for screenshots. For numbers use `measure.thd`. |
| `c.dynamic_dc(temperature)` | Draws node voltages on the schematic. |
| `c.dynamic_ac(freq)` | Draws amplitude and phase of every node at one frequency. |
| `c.run("ac")` | Run with the settings currently in the file. |

Curves are MC9 expressions: `v(Ua)`, `db(v(Ua)/v(Ue))`, `ph(...)`, `mag(...)`, `i(R1)`, `v(R1)` (voltage across a part),
`HARM(v(Ua))` ... A bare string means "y against the analysis' default x" (`T`, `F`, `DCINPUT1`); use `("F", "expr")` to be explicit.

```python
r = c.transient(10e-3, 8e-3, points=2001, curves=["v(Ue)", "v(Ua)"])
print(r.amplitude("v(Ua)"))             # (max-min)/2 in the window
r = c.dc("V2", 0, 20, 0.5, ["v(out)"], temp=[0, 25, 50])
for run in r.runs: print(run.label, run.peak("v(out)"))
```

!!! warning "AC sweep type"
    With MC9's default `Sweep type = Auto`, the numeric table is **coarse and linearly spaced** (e.g. 51 points between 1 Hz
    and 20 MHz) and MC9's cursors interpolate between those points. Band edges read that way can be wrong by more than 10 %.
    `c.ac()` therefore always writes a log sweep with 401 points; `c.run("ac")` warns if you configured `Auto`.
    Check convergence by doubling `points`.

!!! note "Numeric precision"
    MC9 prints six significant digits. That is plenty for gains and bandwidths and for THD down to about 0.01 %.
