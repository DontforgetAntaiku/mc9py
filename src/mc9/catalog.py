"""Component catalog: pins, shapes and attribute conventions, read from the bundled base template."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import cir as cirmod
from . import workspace

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
    defs: list = field(default_factory=list)         # [shapedef]/[compdef] sections to copy into a circuit (parts MC9 taught us)


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


def user_file() -> Path:
    """Where parts learned from MC9 are kept (one .cir-style file of [shapedef]/[compdef] sections)."""
    return workspace.home() / "parts.cir"


def _shape_deps(secs: dict[str, cirmod.Section], name: str, out: list[str], depth: int = 0) -> None:
    s = secs.get(name)
    if s is None or name in out or depth > 6:
        return
    out.append(name)
    for ln in s.lines:
        m = re.match(r'Root="([^"]+)"', ln)
        if m:
            _shape_deps(secs, m.group(1), out, depth + 1)


def _kind_from(s: cirmod.Section, shapes: dict[str, cirmod.Section], base_shapes: set[str]) -> Kind:
    pins, order = {}, []
    for ln in s.lines:
        if ln.startswith("Pin=") and not ln.startswith("PinCnt"):
            f = ln[4:].split(",")
            if f[1].strip().lstrip("-").isdigit() is False:           # digital/analog marker: Pin="Out",d,x,y,...
                f = [f[0]] + f[2:]
            pins[f[0].strip('"')] = (int(f[1]), int(f[2])); order.append(f[0].strip('"'))
    pts = _shape_points(shapes, s.get("Shape"))
    pts += [(px * 8, py * 8) for px, py in pins.values()]
    xs, ys = [p[0] for p in pts] or [0], [p[1] for p in pts] or [0]
    box = (min(xs), min(ys), max(xs), max(ys))
    if len(pins) >= 3:                       # drawn body may stick out past the pins; wires leave at the pins, so clip to them
        px, py = [v[0] * 8 for v in pins.values()], [v[1] * 8 for v in pins.values()]
        box = (max(box[0], min(px)), max(box[1], min(py) - (8 if min(py) == max(py) else 0)),
               min(box[2], max(px)), min(box[3], max(py) + (8 if min(py) == max(py) else 0)))
    name = s.get("Name")
    return Kind(name, pins, order, BODY.get(name, box), VALUE_ATTR.get(name))


def load() -> dict[str, Kind]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    c = cirmod.Cir.load(str(BASE))
    shapes = {s.get("Name"): s for s in c.sections if s.name == "shapedef"}
    base_shapes = set(shapes)
    kinds: dict[str, Kind] = {}
    for s in c.sections:
        if s.name == "compdef":
            kinds[s.get("Name")] = _kind_from(s, shapes, base_shapes)
    uf = user_file()
    if uf.exists():                                     # parts MC9 itself wrote out for us (see learn())
        u = cirmod.Cir.load(str(uf))
        ushapes = {s.get("Name"): s for s in u.sections if s.name == "shapedef"}
        allshapes = {**shapes, **ushapes}
        for s in u.sections:
            name = s.get("Name")
            if s.name != "compdef" or name in kinds:
                continue
            k = _kind_from(s, allshapes, base_shapes)
            need: list[str] = []
            _shape_deps(allshapes, s.get("Shape"), need)
            k.defs = [allshapes[n] for n in reversed(need) if n not in base_shapes] + [s]
            k.value_attr = "VALUE" if name in {"VofV", "Switch", "Transformer", "User Source"} else "MODEL"
            kinds[name] = k
    _CACHE = kinds
    return kinds


def with_value_attr(k: Kind, attr: str) -> Kind:
    return Kind(k.name, k.pins, k.pin_order, k.bbox, attr, k.shape_lines, k.defs)


def learn(names, timeout: float = 180.0) -> list[str]:
    """Ask the installed MC9 for the definitions (shape, pins) of library parts and remember them.

    MC9 resolves a part by name when a circuit mentions it and writes the definition when the circuit is saved; that file is
    read and its [shapedef]/[compdef] sections are kept in ``parts.cir`` next to your circuits. Returns the names that were learned
    (names MC9 does not know are skipped). Needs MC9, takes about half a minute."""
    global _CACHE
    from . import ui
    names = [n for n in names if n]
    c = cirmod.Cir.load(str(BASE))
    i = max(j for j, s in enumerate(c.sections) if s.name == "Circuit") + 1
    probe = []
    for k, n in enumerate(names):
        probe.append(cirmod.Section("Comp", [f"Name={n}", f"Grid={60 + 14 * (k % 6)},{50 + 16 * (k // 6)}", "Rot=0"]))
        probe.append(cirmod.Section("Attr", [f"ONV=0,0,PART,P{k}", "Style=8192"]))
    c.sections[i:i] = probe
    path = workspace.path("parts_learn")
    c.save(str(path))
    m = ui.MC9("parts_learn")
    try:
        m.save()
    finally:
        m.close()
    got = cirmod.Cir.load(str(path))
    uf = user_file()
    mine = cirmod.Cir.load(str(uf)) if uf.exists() else cirmod.Cir("")
    have = {(s.name, s.get("Name")) for s in mine.sections}
    base = cirmod.Cir.load(str(BASE))
    in_base = {(s.name, s.get("Name")) for s in base.sections if s.name in ("shapedef", "compdef")}
    learned = []
    for s in got.sections:
        key = (s.name, s.get("Name"))
        if s.name in ("shapedef", "compdef") and key not in in_base and key not in have:
            mine.sections.append(s)
            have.add(key)
            if s.name == "compdef":
                learned.append(s.get("Name"))
    uf.parent.mkdir(parents=True, exist_ok=True)
    mine.save(str(uf))
    _CACHE = None
    return learned


def resolve(kind: str) -> Kind:
    k = load()
    name = ALIASES.get(kind, kind)
    if name not in k:
        from .config import config
        if config.learn_parts:
            try:
                learn([name])
            except Exception as e:  # noqa: BLE001 - MC9 may be unavailable (offline use): fall through to the error below
                import warnings
                warnings.warn(f"could not ask MC9 for part {name!r}: {e}", stacklevel=2)
            k = load()
    if name not in k:
        raise KeyError(f"unknown component kind {kind!r}; known: {sorted(k)} aliases: {sorted(ALIASES)}. "
                       "A part of MC9's library is fetched automatically when MC9 is available (mc9.config.learn_parts).")
    return k[name]
