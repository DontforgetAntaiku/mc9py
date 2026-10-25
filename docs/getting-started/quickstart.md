# Quickstart

Everything below runs a real MC9 and returns its own numbers and pictures. Each analysis takes 15-30 seconds.

## Describe a circuit, let `mc9` draw and simulate it

```python
import mc9
from mc9 import Netlist, measure, sources

n = Netlist()
n.V("V1", "in", "0", sources.sine(0.1, 1e3))       # name, + node, - node, value
n.R("R1", "in", "out", "1k")
n.C("C1", "out", "0", "159.155n")                   # RC low-pass, fc = 1 kHz

c = n.build("rc")                                   # place parts, route wires, write the circuit -> mc9.Circuit

op = c.op()                                         # DC operating point
print(op.nodes)                                     # {'IN': 0.0, 'OUT': 0.0}

r = c.ac(10, 1e5, 401, ["db(v(out))"])              # AC sweep (always logarithmic)
bw = measure.bandwidth(c, "db(v(out))", cursors=True)   # -3 dB point; MC9's cursors are put on it
print(f"{bw.f_high:.1f} Hz")                        # ~998 Hz

c.shot("rc_ac.png")                                 # MC9's own plot incl. its cursor table
c.dynamic_dc(25)
c.shot("rc_dc.png", "schematic")                    # schematic with node voltages
c.close()
```

Pictures and numeric output are written to the work folder (`mc9.exchange_dir()`).

## Use an existing circuit

```python
c = mc9.open("my_lab/amplifier.cir")      # copied into the work folder; your file is never modified
print(c.parts())                           # {'R1': {'type': 'Resistor', 'RESISTANCE': '200'}, ...}
c.set("R2", "RESISTANCE", "180k")          # edit a value
r = c.ac(1, 2e7, 801, ["db(v(Ua)/v(Ue))"])
c.cursors(1e3, 1e4)
c.shot("response.png")
c.export("my_lab/amplifier_v2.cir")        # save the edited circuit to a NEW file (never overwrites)
```

## Place parts yourself

```python
s = mc9.Schematic()
v = s.add("V", "V1", "DC 10", at=(0, 8), rot=3)
r1 = s.add("R", "R1", "1k", at=(10, 2))
r2 = s.add("R", "R2", "2k", at=(26, 2), rot=1)
g = s.add("GND", None, at=(26, 14))
s.wire(v.Plus, r1.Minus); s.wire(r1.Plus, r2.Minus); s.wire(r2.Plus, g.PinA)
s.wire(v.Minus, (0, 14)); s.wire((0, 14), g.PinA)
c = s.build("divider")
```

## Let an AI assistant do it

```bash
pip install "mc9py[mcp]"
claude mcp add microcap9 -- mc9 mcp        # or add `mc9 mcp` to any MCP client
```
See [MCP server](../guide/mcp.md).
