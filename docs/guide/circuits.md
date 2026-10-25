# Circuits

A `Circuit` is a circuit file living in the work folder together with (at most) one running MC9 instance.

```python
c = mc9.open("lab/lr2.cir", name="lr2")      # import: copy into the work folder (name optional)
c = mc9.attach("lr2")                          # re-use a circuit already in the work folder (built or imported earlier)
with mc9.open("lab/lr2.cir") as c: ...         # closes MC9 on exit;  mc9.close_all() closes everything
```

Your original file is only ever *read*. Circuits built by `Schematic`/`Netlist` are written straight into the work folder.

## Parts

```python
c.parts()                          # {'R1': {'type': 'Resistor', 'RESISTANCE': '200'}, 'Q1': {'type': 'NPN', 'MODEL': 'BF420', ...}}
c.get("R2", "RESISTANCE")          # '233.2k'
c.set("R2", "RESISTANCE", "180k")  # returns the old value; numbers work too:  c.set("V2", "VALUE", 21.6)
```

Edits are held in memory and written before the next run. A changed file restarts MC9 automatically (about 10 s).

## Raw settings

```python
c.limits("ac")                              # read the [Limits] keys of an analysis
c.limits("transient", TRange="10m,5m", NPts=2001)   # set raw keys
c.curves("ac", "db(v(Ua)/v(Ue))", ("F", "ph(v(Ua)/v(Ue))"))   # replace the curve list ('y' or (x, y))
c.show(voltages=True, currents=False)       # what dynamic analyses draw on the schematic
```

Most people use the friendly methods in [Analyses](analyses.md) instead.

## Saving

```python
c.export("~/labs/amplifier_v2.cir")     # writes a new file; raises FileExistsError instead of overwriting
```
