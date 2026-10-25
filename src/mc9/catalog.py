"""Component catalog: pins, shapes and attribute conventions, read from the bundled base template."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import cir as cirmod

BASE = Path(__file__).parent / "templates" / "base.cir"

# friendly aliases -> MC9 compdef names; value attribute name per component
ALIASES = {"R": "Resistor", "C": "Capacitor", "L": "Inductor", "V": "Voltage Source", "VB": "Battery",
           "I": "Current Source", "D": "Diode", "Q": "NPN", "QP": "PNP", "GND": "Ground", "OPAMP": "Opamp",
           "VSIN": "Voltage Source", "VPULSE": "Voltage Source", "M": "NMOS"}
VALUE_ATTR = {"Resistor": "RESISTANCE", "Capacitor": "CAPACITANCE", "Inductor": "INDUCTANCE",
              "Voltage Source": "VALUE", "Battery": "VALUE", "Current Source": "VALUE", "Sine Source": "VALUE",
              "Pulse Source": "VALUE", "Diode": "MODEL", "NPN": "MODEL", "PNP": "MODEL", "NMOS": "MODEL",
              "Opamp": "MODEL", "BF420": "MODEL"}


def transform(x: float, y: float, rot: int) -> tuple[float, float]:
    """MC9 rotation: 0..3 = 0/90/180/270 deg clockwise (y down); 4..7 = mirrored (y -> -y) first."""
    if rot >= 4:
        y = -y
    for _ in range(rot % 4):
        x, y = -y, x
    return x, y


@dataclass
class Kind:
    name: str
    pins: dict[str, tuple[int, int]]            # grid units, unrotated
    pin_order: list[str]
    bbox: tuple[float, float, float, float]     # design px (8 px = 1 grid), unrotated: x0,y0,x1,y1
    value_attr: str | None
    shape_lines: list[str] = field(default_factory=list)


def _shape_points(secs: dict[str, cirmod.Section], name: str, dx=0, dy=0, depth=0) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    s = secs.get(name)
    if s is None or depth > 4:
        return pts
    for ln in s.lines:
        key, _, val = ln.partition("=")
        nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", val)] if key != "Root" else []
        if key == "Line" and len(nums) >= 4:
            pts += [(nums[0] + dx, nums[1] + dy), (nums[2] + dx, nums[3] + dy)]
        elif key in ("Ellipse", "Rectangle", "Arc", "Box") and len(nums) >= 4:
            pts += [(nums[0] + dx, nums[1] + dy), (nums[2] + dx, nums[3] + dy)]
        elif key == "PolyLine" and len(nums) >= 2:
            pts.append((nums[0] + dx, nums[1] + dy))
        elif key == "Root":
            m = re.match(r'"([^"]+)",\s*(-?\d+),\s*(-?\d+)', val)
            if m:
                pts += _shape_points(secs, m.group(1), dx + int(m.group(2)), dy + int(m.group(3)), depth + 1)
    return pts


# hand-tuned body boxes (design px, unrotated: x0,y0,x1,y1), measured from MC9 renderings
BODY = {"Resistor": (0, -5, 48, 5), "Capacitor": (0, -8, 48, 8), "Inductor": (0, -8, 48, 8),
        "Battery": (0, -8, 48, 8), "Diode": (0, -8, 48, 8), "Voltage Source": (0, -12, 48, 12),
        "Sine Source": (0, -12, 48, 12), "Pulse Source": (0, -12, 48, 12), "Current Source": (-12, 0, 12, 48),
        "NPN": (0, -24, 24, 24), "PNP": (0, -24, 24, 24), "BF420": (0, -24, 24, 24), "NMOS": (0, -24, 24, 24),
        "Opamp": (0, -8, 72, 56), "Ground": (0, -8, 24, 8)}

_CACHE: dict[str, Kind] | None = None


def load() -> dict[str, Kind]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    c = cirmod.Cir.load(str(BASE))
    shapes = {s.get("Name"): s for s in c.sections if s.name == "shapedef"}
    kinds: dict[str, Kind] = {}
    for s in c.sections:
        if s.name != "compdef":
            continue
        pins, order = {}, []
        for ln in s.lines:
            if ln.startswith("Pin=") and not ln.startswith("PinCnt"):
                f = ln[4:].split(",")
                pins[f[0].strip('"')] = (int(f[1]), int(f[2])); order.append(f[0].strip('"'))
        pts = _shape_points(shapes, s.get("Shape"))
        pts += [(px * 8, py * 8) for px, py in pins.values()]
        xs, ys = [p[0] for p in pts] or [0], [p[1] for p in pts] or [0]
        name = s.get("Name")
        kinds[name] = Kind(name, pins, order, BODY.get(name, (min(xs), min(ys), max(xs), max(ys))), VALUE_ATTR.get(name))
    _CACHE = kinds
    return kinds


def resolve(kind: str) -> Kind:
    k = load()
    name = ALIASES.get(kind, kind)
    if name not in k:
        raise KeyError(f"unknown component kind {kind!r}; available: {sorted(k)} aliases: {sorted(ALIASES)}")
    return k[name]
