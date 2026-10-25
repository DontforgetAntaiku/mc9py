"""SPICE-like circuit description -> automatically placed schematic.

    n = mc9.Netlist()
    n.V("V1", "in", "0", sources.sine(0.01, 1e3))        # name, plus node, minus node, value
    n.R("R1", "in", "base", "200")
    n.C("C1", "base", "b", "3.47u")
    n.R("R2", "vcc", "b", "233.2k")
    n.Q("Q1", c="col", b="b", e="0", model="BF420")
    n.R("R3", "vcc", "col", "1.2k")
    n.C("C3", "col", "out", "553n"); n.R("R4", "out", "0", "1.2k")
    n.VB("V2", "vcc", "0", "18")
    c = n.build("ce_stage")          # places parts, routes wires, adds labels, writes the circuit -> mc9.Circuit

Nodes are names; "0" / "gnd" is ground. Every node whose name you gave gets a label in the schematic (so `v(out)`
works in curves). Node names starting with "_" stay unlabelled.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import catalog

GROUND = {"0", "gnd", "GND", "ground"}

# netlist argument order -> pin names (two-terminal parts: first node = first pin below)
PINS = {
    "Resistor": ("Minus", "Plus"), "Capacitor": ("Minus", "Plus"), "Inductor": ("Minus", "Plus"),
    "Voltage Source": ("Plus", "Minus"), "Battery": ("Plus", "Minus"), "Current Source": ("Plus", "Minus"),
    "Diode": ("Anode", "Cathode"),
    "NPN": ("Collector", "Base", "Emitter"), "PNP": ("Collector", "Base", "Emitter"),
    "NMOS": ("Drain", "Gate", "Source", "Body"),
    "Opamp": ("Plus input", "Minus input", "Output", "VCC", "VEE"),
}


# Transistor-like parts the placer can put on the signal path: (control pin, output pin, reference pin)
ROLES = {
    "NPN": ("Base", "Collector", "Emitter"), "PNP": ("Base", "Collector", "Emitter"),
    "NPN4": ("Base", "Collector", "Emitter"), "PNP4": ("Base", "Collector", "Emitter"),
    "IGBT": ("Gate", "Collector", "Emitter"),
    "NMOS": ("Gate", "Drain", "Source"), "PMOS": ("Gate", "Drain", "Source"),
    "DNMOS": ("Gate", "Drain", "Source"), "DPMOS": ("Gate", "Drain", "Source"),
    "NJFET": ("Gate", "Drain", "Source"), "PJFET": ("Gate", "Drain", "Source"), "GaAsFET": ("Gate", "Drain", "Source"),
}
ALIASES_EXTRA = {"J": "NJFET", "JP": "PJFET", "MP": "PMOS", "Z": "Zener", "SCR": "SCR", "TRIAC": "Triac",
                 "E": "VofV", "SW": "Switch", "T": "Transformer", "X": None}

# attribute that holds the visible value of parts the base template does not know (anything else: MODEL)
VALUE_PARTS = {"VofV", "Switch", "Transformer", "Battery", "Current Source", "Voltage Source", "Pulse Source", "Sine Source", "User Source"}


@dataclass
class NPart:
    kind: catalog.Kind
    name: str
    nets: dict[str, str]                 # pin name -> node name
    value: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def two_terminal(self) -> bool:
        return len(self.kind.pins) == 2


class Netlist:
    def __init__(self):
        self.parts: list[NPart] = []

    # ---- adding parts -------------------------------------------------------------------------
    def add(self, kind: str, name: str, nodes, value: str | None = None, **extra) -> NPart:
        """Any MC9 part by name. ``nodes``: a list in pin order, or a dict ``{"Drain": "d", "Gate": "g", ...}``.

        Parts that are not in the built-in set (JFETs, PMOS, Zener, transformers, controlled sources, switches, logic, macros ...)
        are fetched from MC9 itself the first time they are used (see ``mc9.catalog.learn``)."""
        k = catalog.resolve(ALIASES_EXTRA.get(kind) or kind)
        pins = PINS.get(k.name, tuple(k.pin_order))
        if isinstance(nodes, dict):
            missing = [pin for pin in pins if pin not in nodes]
            if missing or len(nodes) != len(pins):
                raise ValueError(f"{name}: {k.name} pins are {pins}; got {tuple(nodes)}")
            nodes = [nodes[pin] for pin in pins]
        if len(nodes) != len(pins):
            raise ValueError(f"{name}: {k.name} needs {len(pins)} nodes {pins}, got {len(nodes)}")
        nets = dict(zip(pins, map(str, nodes)))
        at: dict[tuple, str] = {}
        for pin, node in nets.items():                       # pins drawn on the same grid point are one connection in MC9
            other = at.setdefault(k.pins[pin], pin)
            if other != pin and nets[other] != node:
                raise ValueError(f"{name}: MC9 draws pins {other!r} and {pin!r} of {k.name} on the same point, so they are always "
                                 f"the same node ({nets[other]!r} != {node!r}); connect them to the same node")
        attr = extra.pop("value_attr", None)
        if attr:
            k = catalog.with_value_attr(k, attr)
        if value is None and k.value_attr in extra:
            value = extra.pop(k.value_attr)
        p = NPart(k, name, dict(zip(pins, map(str, nodes))), value, extra)
        self.parts.append(p)
        return p

    def R(self, name, n1, n2, value): return self.add("R", name, [n1, n2], value)
    def C(self, name, n1, n2, value): return self.add("C", name, [n1, n2], value)
    def L(self, name, n1, n2, value): return self.add("L", name, [n1, n2], value)
    def V(self, name, plus, minus, value): return self.add("V", name, [plus, minus], value)
    def VB(self, name, plus, minus, value): return self.add("VB", name, [plus, minus], value)
    def I(self, name, plus, minus, value): return self.add("I", name, [plus, minus], value)  # noqa: E743
    def D(self, name, anode, cathode, model="1N4148"): return self.add("D", name, [anode, cathode], model)
    def Q(self, name, c, b, e, model): return self.add("Q", name, [c, b, e], model)
    def QP(self, name, c, b, e, model): return self.add("QP", name, [c, b, e], model)
    def M(self, name, d, g, s, body, model): return self.add("M", name, [d, g, s, body], model)
    def J(self, name, d, g, s, model): return self.add("J", name, [d, g, s], model)             # N-channel JFET
    def JP(self, name, d, g, s, model): return self.add("JP", name, [d, g, s], model)           # P-channel JFET
    def MP(self, name, d, g, s, body, model): return self.add("MP", name, [d, g, s, body], model)   # PMOS
    def Z(self, name, anode, cathode, model="1N752"): return self.add("Z", name, [anode, cathode], model)   # Zener
    def E(self, name, out_p, out_m, in_p, in_m, gain): return self.add("E", name, [out_p, out_m, in_p, in_m], gain)  # VCVS
    def SW(self, name, out_p, out_m, in_p, in_m, model): return self.add("SW", name, [out_p, out_m, in_p, in_m], model)  # switch
    def OPAMP(self, name, plus, minus, out, vcc, vee, model="LM741"): return self.add("OPAMP", name, [plus, minus, out, vcc, vee], model)

    # ---- queries --------------------------------------------------------------------------------
    def nodes(self) -> list[str]:
        seen: list[str] = []
        for p in self.parts:
            for n in p.nets.values():
                if n not in seen:
                    seen.append(n)
        return seen

    @staticmethod
    def is_ground(node: str) -> bool:
        return node in GROUND

    def build(self, name: str, labels: str = "dc", chars: int | None = None, **options):
        """Place + route + write the circuit; returns an `mc9.Circuit`.

        `labels` / `chars` as in `Schematic.build` (room for MC9's voltage boxes); other options as in `autoplace.place`
        (`mode`, `gap`, `input`, `output`, `rails_as_labels`, `ground_labels`)."""
        from .autoplace import place
        options.setdefault("mode", "ac" if labels == "ac" else "dc")
        return place(self, **options).build(name, labels=labels, chars=chars)

    def schematic(self, **options):
        """The placed `Schematic` (inspect/adjust before `.build()`)."""
        from .autoplace import place
        return place(self, **options)
