# Building schematics

`mc9.Schematic` writes MC9 circuit files from code, with automatic **label placement** that avoids collisions with MC9's own
voltage boxes - so screenshots of Dynamic DC / AC look clean without hand-tuning.

```python
s = mc9.Schematic()
q  = s.add("Q",  "Q1", at=(46, 10), MODEL="BF420")          # kind, name, value, position (grid), rotation, extra attributes
r1 = s.add("R",  "R1", "200", at=(8, 10))
gnd = s.add("GND", None, at=(54, 17))
s.wire(r1.Plus, q.Base)                  # pins by name: part.Plus, part.Base, part.pin("Plus input")
s.node("Ue", (12, 10))                   # name a node (label; usable in curves: v(Ue))
c = s.build("amp", labels="dc")          # auto-place labels, centre + zoom the drawing, write it, return a Circuit
```

## Parts

| kind | MC9 part | value attribute | pins |
|---|---|---|---|
| `R` `C` `L` | Resistor, Capacitor, Inductor | `RESISTANCE` `CAPACITANCE` `INDUCTANCE` | `Minus`, `Plus` |
| `V` | SPICE voltage source (`DC 0 AC 1 0 Sin ...`, see `mc9.sources`) | `VALUE` | `Plus`, `Minus` |
| `VB` | Battery | `VALUE` | `Plus`, `Minus` |
| `I` | Current source | `VALUE` | `Plus`, `Minus` |
| `D` | Diode | `MODEL` | `Anode`, `Cathode` |
| `Q` `QP` | NPN / PNP | `MODEL` | `Collector`, `Base`, `Emitter` |
| `M` | NMOS | `MODEL` | `Drain`, `Gate`, `Source`, `Body` |
| `OPAMP` | op-amp | `MODEL` | `Plus input`, `Minus input`, `Output`, `VCC`, `VEE` |
| `GND` | ground | - | `PinA` |

Any other component definition in `mc9/templates/base.cir` can be used by its MC9 name. Model names (`BF420`, `1N4148`,
`LM741`) are resolved by MC9's own library, so they must exist there.

## Geometry

- One **grid unit** = 8 design px = 16 screen px. Coordinates are integers; pins sit on grid points.
- `rot` 0/1/2/3 = pointing right / down / left / up; 4-7 are the mirrored versions. Ground symbols hang downward by default.
- A resistor is 6 units long; a transistor is 3 units wide and tall; an op-amp is 9 x 7.
- `wire(a, b)` accepts points or pins; if they are not aligned it draws an L (`via="h"` or `"v"` chooses the corner).

## What MC9 requires (and the library enforces)

- Wires join **only at endpoints and pins**. The library splits T-junctions for you, and also at node-name points.
- Every node needs a **DC path to ground** (capacitors and current sources do not count).
- A node name attaches only at an endpoint/pin; equally named nodes are **one node**, and all Ground symbols are node 0.
- Circuits get valid default curves so the first analysis works without configuration.

```python
s.check()          # unwired pins, crossing wires, nodes without DC path to ground
s.audit("dc")      # predicted collisions: labels, node names, MC9's voltage boxes, bodies
s.audit("ac")      # Dynamic AC boxes ('281.418m,172.755') are ~12 grid units wide: keep voltage nodes >= 14 apart
s.pin_nets()       # {(part, pin): net id} exactly as MC9 will join them - compare with your intended netlist
```

`build()` calls `check()` and `audit()` and warns about every problem it finds. Pass `chars=` when your voltage values are
short or long (default width: 8 characters for `dc`, 17 for `ac`).

## Where MC9 draws voltages

One box per non-ground node, centred on the **first pin of that node** (component order); for a **named** node the box hangs
below-right of the name point. Name nodes on free wire points, not on pins, or the name will overlap the part body.

## Zoom and position

The drawing is centred in MC9's canvas at 2x zoom; if it is wider than ~100 grid units (labels included) it switches to 1x.
`Schematic.zoom` and `crop_px` are available after `build()`, and `c.shot(..., "schematic")` uses them to crop tightly.
