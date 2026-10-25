# Stepping, temperatures, Monte Carlo, optimizer

One analysis can run many times. Every run keeps what it used (`run.params`), and every plot is still MC9's own.

## Stepping

```python
c = mc9.library.rc_lowpass().build("rc")
c.step("R1", "1k", "3k", "1k")                 # R1 = 1k, 2k, 3k          (linear)
c.step("C1", "100n,159n")                      # a list
c.step("R1", 100, 1e5, 10, method="log")       # multiply by 10 each run
c.step("BF420", 100, 400, 100, param="BF", kind="model")   # a model parameter
r = c.ac(10, 1e5, 401, ["db(v(out))"])

for run in r.runs:
    print(run.params, run.cross("db(v(out))", -3.0103))      # {'Temperature': 25.0, 'R1': 1000.0} [1000.2]
r.select(R1=2000)                              # the runs where R1 was 2k
c.stepping_mode(nested=False)                  # all variables change together instead of every combination
c.clear_steps()                                # stepping off
```

`analysis="ac"` (or `"transient"`, `"dc"`, `"distortion"`) limits a step to one analysis; the default is all four. Up to 20 variables.
Stepping is written to the circuit as MC9's own `[Stepping]` sections, so it works with both engines.

## Temperatures

```python
c.dc("V2", 0, 20, 2, curves=["v(col)"], temp=[0, 25, 75])    # one run per temperature
c.transient(5e-3, temp=[0, 85])
```

A temperature list stays in the analysis settings until you give a single value again (`temp=25`). With stepping or Monte Carlo
the runs are the product: 3 temperatures x 4 Monte Carlo cases = 12 runs.

## Monte Carlo

```python
c.tolerance("R1", lot="5%")                    # a resistor, capacitor or inductor (or dev="1%" per device)
c.monte_carlo(runs=50, distribution="normal", seed=1, analysis="transient")
r = c.transient(5e-3, curves=["v(out)"])       # 50 runs, 'Case=1' is the nominal circuit
spread = [run["v(out)"][-1] for run in r.runs]
```

`distribution`: `"normal"` or `"worst case"`. `c.model(".MODEL ...")` adds any netlist text (models, `.DEFINE`, `.PARAMETERS`) to the circuit.

## Optimizer (native engine)

```python
res = c.optimize({"R1": (100, 5000)},                               # up to 4 parts and their limits
                 [("equals", "Y_Level(db(v(out)),1,1,2000)", -3.0103)],   # up to 4 goals
                 analysis="ac")
res["params"]["R1"]["value"]                                        # '500'  - also applied to the circuit
```

Goal kinds: `"equals"` (needs a target), `"minimize"`, `"maximize"`. The optimizer is MC9's own (Powell); it is driven through its
dialog by the DLL, so it needs the native engine.

## Curves and FFT

```python
c.curves("ac", dict(y="db(v(out))", xrange=(10, 1e5), yrange=(-60, 5), color="#FF0000"))
c.transient(10e-3, curves=["v(out)", ("F", "db(mag(fft(v(out))))")])   # a second plot: MC9's FFT
```

## Monte Carlo histogram, statistics and plot commands (native engine)

```python
c.tolerance("R1", lot="10%"); c.tolerance("C1", lot="5%")
c.monte_carlo(runs=100, seed=1, analysis="transient")
c.histogram("Y_Level(v(out),1,1,10m)")                  # any MC9 performance expression
r = c.transient(10e-3, curves=["v(out)"])
c.show_histogram("hist.png")                            # MC9's own histogram window: bars, min / mean / max / sigma
from mc9 import measure
measure.statistics(measure.per_run(r, lambda run: run.peak("v(out)")[1]), lo=0.68, hi=0.78)   # your own numbers, with the yield

c.cursor_case(5)                # cursor on Monte Carlo / stepping case 5
c.autoscale(); c.restore_scale(); c.normalize_y("max")
c.cursors_y(0.2, 0.4)           # cursors at Y values
c.command("fill_scatter")       # any known command by name: see mc9.native.KNOWN_IDS
```

`KNOWN_IDS` also holds the numbers of the stepping (F11), limits (F9), watch window, breakpoints, operating-point methods,
numeric output, initial-condition editor and "reduce points" commands; `c.command(name)` opens them, and
`tools/probe_menus.py` maps further menu items (it clicks an item while the hook records the command and the dialogs).
