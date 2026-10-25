# Results and data

Every analysis returns a `Result` - the numbers MC9 wrote to its numeric output - with helpers for the things you normally
read off the screen with cursors.

```python
r = c.ac(1, 2e7, 801, ["db(v(Ua)/v(Ue))", "ph(v(Ua)/v(Ue))"])
r.columns                       # ['F', 'db(v(Ua)/v(Ue))', 'ph(v(Ua)/v(Ue))']
r.x                             # first column (frequency)
r["db(v(Ua)/v(Ue))"]            # a column as a list of floats
```

## Reading values

| Method | Meaning |
|---|---|
| `r.value_at(col, x)` | y at x, interpolated (in log-x for wide AC sweeps, linear otherwise) |
| `r.cross(col, level, edge=None)` | all x where the curve crosses `level`; `edge="rising"` or `"falling"` |
| `r.peak(col, xmin, xmax)` / `r.trough(...)` | `(x, y)` of the maximum / minimum in a window |
| `r.amplitude(col, xmin, xmax)` | (max - min) / 2, handy for sine amplitudes in steady state |
| `r.mean(col, xmin, xmax)` | average |
| `r.to_csv(path)` | export |

```python
g = "db(v(Ua)/v(Ue))"
f0, g0 = r.peak(g)                              # centre frequency and gain
f_low = [f for f in r.cross(g, g0 - 3) if f < f0][-1]
```

## Several runs

Temperature lists and stepping produce several tables; they are in `r.runs` (each a `Run` with the same helpers and a `label`):

```python
r = c.dc("V1", 0, 1, 0.01, ["i(D1)"], temp=[-25, 0, 25, 50, 75])
for run in r.runs:
    print(run.label, run.value_at("i(D1)", 0.7))
```

A `Result` behaves like its first run (`r["col"]`, `r.peak(...)`).

## Operating point

```python
op = c.op()
op.nodes                 # {'IN': 0.0, 'OUT': 6.667, '3': 0.695}   (named nodes, numbers for the rest)
op.v("out")              # case-insensitive
op["Q1"]["IC"]           # device values: IB IC VBE VCE BETADC GM RPI RO CPI CMU FT ... PD (power)
op["R3"]["PD"], op["R3"]["Ir"]
```

## Number format

MC9 prints values with SI suffixes (`1.5K`, `4.7u`, `2MEG`); the parser converts them. A cell that MC9 prints as `N/A`
(for example the phase at DC) becomes `nan`.
