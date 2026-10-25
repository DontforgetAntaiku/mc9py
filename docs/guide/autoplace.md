# Automatic placement

Describe the circuit like a SPICE netlist and let `mc9` place the parts, route the wires and set the labels.

```python
n = mc9.Netlist()
n.V("V1", "src", "0", sources.sine(3.5e-3, 2224))
n.R("R1", "src", "ue", "200")
n.C("C1", "ue", "b", "3.47u")
n.R("R2", "vcc", "b", "233.2k")
n.Q("Q1", c="col", b="b", e="0", model="BF420")
n.R("R3", "vcc", "col", "1.2k")
n.C("C2", "col", "0", "12n")
n.C("C3", "col", "ua", "553n")
n.R("R4", "ua", "0", "1.2k")
n.VB("V2", "vcc", "0", "18")

c = n.build("ce_stage")                  # -> mc9.Circuit, drawn and ready
```

`"0"` (or `gnd`) is ground. Every node you name appears as a node label in the schematic, so `v(ua)` works in curves; names
starting with `_` stay unlabelled. Two-terminal parts take their nodes in order (`R`, `C`, `L`: first node on the left;
`V`, `VB`, `I`: plus first; `D`: anode first); transistors are `Q(name, c, b, e, model)`, op-amps
`OPAMP(name, plus, minus, out, vcc, vee, model)`.

## How it places things

1. **Classify** nodes: ground, supply rails (DC sources to ground), the input (the first source with `Sin`/`Pulse`/`AC`) and the
   output (the node farthest along the signal path that is not an active device's input).
2. The **backbone** - shortest signal path from input to output - runs left to right. Transistors are traversed base to
   collector, op-amps input to output.
3. Everything else **hangs off backbone nodes**: parts to ground go down, parts to a rail go up, series chains are stacked,
   side pins (emitter, second op-amp input) get their own branches. Parts joining two existing nodes (feedback) become
   **bridges** above the circuit.
4. **Ground and rails are buses**; sources sit at the ends. If a drawing would cross wires, that net falls back to
   **named labels** (MC9 treats equally named nodes as one net) - always electrically correct, never a crossing.
5. The result is checked (`check`, `audit`, **connectivity equivalence** with your netlist) and re-spaced if boxes or labels would
   collide.

```python
s = n.schematic(mode="ac")        # inspect before writing; mode="ac" leaves room for phasor boxes
print(s.notes)                    # anything unusual ("U1 could not be placed", ...)
c = s.build("ce_stage", labels="ac")
```

Options: `mode="dc"|"ac"`, `gap=` (minimum wire length), `input=`, `output=` (override detection), `rails_as_labels=True`,
`ground_labels=True` (a ground symbol on every ground pin instead of a bus).

## Limits

The placer targets the usual teaching circuits: dividers, RC/RL/RLC networks, diode clippers and rectifiers, single transistor
stages (with feedback), op-amp stages. Large or non-planar circuits may fall back to many labels; multi-pin parts inside
branches (a transistor in a shunt path) are connected by name rather than drawn. Use `Schematic` when you want full control.
Auto-placement never changes the circuit: the tests check that the nets of every generated drawing equal the netlist.

## Starter circuits

`mc9.library` has ready-made teaching circuits as parametrised netlists - handy for learning, demos and tests:

```python
from mc9 import library
c = library.voltage_divider(vin=12, r1="2.2k", r2="1k").build("div")
c = library.ce_amplifier(vcc=15, rc="2.2k").build("amp")          # common-emitter stage with base bias resistor
c = library.inverting_amplifier(gain=20).build("inv")
library.CATALOG                                                   # name -> factory
```

`voltage_divider`, `rc_lowpass`, `rc_highpass`, `rlc_lowpass`, `diode_clipper`, `ce_amplifier`, `ce_feedback_amplifier`,
`inverting_amplifier`, `noninverting_amplifier`.
