"""Build MC9 schematics from Python, with automatic label placement that avoids collisions.

    from mc9 import Schematic
    s = Schematic()
    v = s.add("V", "V1", "DC 10", at=(0, 6), rot=3)            # grid units; (0,0) = top-left of your drawing
    r1 = s.add("R", "R1", "1k", at=(4, 0))
    ...
    s.wire(v.pin("Plus"), r1.pin("Minus"))
    s.node("Ue", r1.pin("Minus"))                               # node name label
    c = s.build("divider", labels="dc")                         # -> mc9.Circuit (centered in MC9's view)

Units: 1 grid = 8 design px = 16 screen px. MC9 draws, per node, one voltage box centered on one of its pins
(dynamic DC/AC); `labels="dc"|"ac"` reserves room for those boxes so part labels never collide with them.
"""
from __future__ import annotations

import copy
import itertools
from dataclasses import dataclass, field

from . import catalog
from . import cir as cirmod
from . import workspace

TEXT_H = 9.0          # label height, design px
CHAR_W = 7.0          # label char width, design px
Rect = tuple[float, float, float, float]


def _overlap(a: Rect, b: Rect) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def _inflate(r: Rect, m: float) -> Rect:
    return (r[0] - m, r[1] - m, r[2] + m, r[3] + m)


@dataclass
class Part:
    kind: catalog.Kind
    name: str | None
    value: str | None
    at: tuple[int, int]
    rot: int
    extra: dict = field(default_factory=dict)
    part_label: tuple[int, int] = (0, 0)
    value_label: tuple[int, int] = (0, 12)
    labels_fixed: bool = False
    index: int = 0

    def pin(self, name: str) -> tuple[int, int]:
        if name not in self.kind.pins:
            raise KeyError(f"{self.kind.name} has pins {self.kind.pin_order}, not {name!r}")
        dx, dy = catalog.transform(*self.kind.pins[name], self.rot)
        return int(self.at[0] + dx), int(self.at[1] + dy)

    def __getitem__(self, name: str) -> tuple[int, int]:
        return self.pin(name)

    def __getattr__(self, name: str):          # part.Plus, part.Base, ...
        if name != "kind" and name in self.__dict__.get("kind", catalog.Kind("", {}, [], (0, 0, 0, 0), None)).pins:
            return self.pin(name)
        raise AttributeError(name)

    def body(self) -> Rect:
        """Absolute body rectangle in design px."""
        x0, y0, x1, y1 = self.kind.bbox
        pts = [catalog.transform(x, y, self.rot) for x in (x0, x1) for y in (y0, y1)]
        ox, oy = self.at[0] * 8, self.at[1] * 8
        return (ox + min(p[0] for p in pts), oy + min(p[1] for p in pts),
                ox + max(p[0] for p in pts), oy + max(p[1] for p in pts))


class Schematic:
    def __init__(self, template: str | None = None):
        self.template = template or str(catalog.BASE)
        self.parts: list[Part] = []
        self.segments: list[tuple[int, int, int, int]] = []
        self.nodes_named: list[tuple[str, tuple[int, int]]] = []
        self.notes: list[str] = []
        self._box_chars = 8
        self.crop_px: tuple[int, int, int, int] | None = None
        self.zoom = 2.0

    # ---- building -----------------------------------------------------------------------------
    def add(self, kind: str, name: str | None, value: str | None = None, at: tuple[int, int] = (0, 0),
            rot: int | None = None, **extra) -> Part:
        """Place a component. kind: 'R','C','L','V','VB','I','D','Q','QP','GND','OPAMP','VSIN','VPULSE','M' or an MC9 name.
        extra: more attributes, e.g. MODEL='BF420' for transistors/diodes."""
        k = catalog.resolve(kind)
        if value is None and k.value_attr in extra:       # e.g. add('Q','Q1', MODEL='BF420')
            value = extra.pop(k.value_attr)
        elif k.value_attr in extra:
            raise ValueError(f"{k.value_attr} given twice for {name}")
        if rot is None:
            rot = 1 if k.name == "Ground" else 0     # ground symbol hangs below its pin
        p = Part(k, name, value, (int(at[0]), int(at[1])), rot, extra, index=len(self.parts))
        self.parts.append(p)
        return p

    def wire(self, a, b, via: str = "h") -> None:
        """Wire two points (grid tuples or Part pins). Not axis-aligned -> L-shaped (via='h': horizontal first)."""
        (x1, y1), (x2, y2) = a, b
        if (x1, y1) == (x2, y2):
            return
        if x1 == x2 or y1 == y2:
            self._seg(x1, y1, x2, y2)
        elif via == "h":
            self._seg(x1, y1, x2, y1); self._seg(x2, y1, x2, y2)
        else:
            self._seg(x1, y1, x1, y2); self._seg(x1, y2, x2, y2)

    def _seg(self, x1, y1, x2, y2) -> None:
        self.segments.append((x1, y1, x2, y2))

    def node(self, name: str, at) -> None:
        """Name a node (shows as a label; use it in expressions: v(Ue))."""
        self.nodes_named.append((name, (int(at[0]), int(at[1]))))

    # ---- connectivity ---------------------------------------------------------------------------
    def _split_wires(self) -> list[tuple[int, int, int, int]]:
        """Split segments at every point lying on their interior (pins and other wire ends) -> real nets."""
        pts = {p.pin(n) for p in self.parts for n in p.kind.pins}
        pts |= {pt for _, pt in self.nodes_named}          # MC9 attaches a node name only at a wire endpoint/pin
        for s in self.segments:
            pts |= {(s[0], s[1]), (s[2], s[3])}
        out = []
        for x1, y1, x2, y2 in self.segments:
            on = sorted({q for q in pts if self._on_segment(q, (x1, y1, x2, y2))},
                        key=lambda q: (q[0] - x1) ** 2 + (q[1] - y1) ** 2)
            for a, b in zip(on, on[1:]):
                out.append((*a, *b))
        return out

    @staticmethod
    def _on_segment(q, s) -> bool:
        x1, y1, x2, y2 = s
        if x1 == x2:
            return q[0] == x1 and min(y1, y2) <= q[1] <= max(y1, y2)
        return q[1] == y1 and min(x1, x2) <= q[0] <= max(x1, x2)

    def nets(self) -> dict[tuple[int, int], int]:
        """point -> net id, as MC9 sees it: wire endpoints are joined, nodes with the same label are one net,
        and all Ground symbols are node 0."""
        parent: dict = {}

        def find(a):
            parent.setdefault(a, a)
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for x1, y1, x2, y2 in self._split_wires():
            parent[find((x1, y1))] = find((x2, y2))
        for p in self.parts:
            for n in p.kind.pins:
                find(p.pin(n))
        by_label: dict[str, tuple] = {}
        for text, pt in self.nodes_named:
            if pt in parent:
                r = by_label.setdefault(text.lower(), pt)
                parent[find(pt)] = find(r)
        grounds = [p.pin("PinA") for p in self.parts if p.kind.name == "Ground"]
        for g in grounds[1:]:
            parent[find(g)] = find(grounds[0])
        return {pt: find(pt) for pt in list(parent)}

    def pin_nets(self) -> dict[tuple[str, str], int]:
        """{(part name, pin): net id} as MC9 will see it (see `nets`). Use it to verify a drawing against a netlist."""
        net = self.nets()
        return {(p.name, pin): net[p.pin(pin)] for p in self.parts if p.name for pin in p.kind.pins}

    def check(self) -> list[str]:
        """Static problems: unconnected pins, wire crossings that don't share an endpoint."""
        issues = []
        net = self.nets()
        members: dict[int, list] = {}
        for pt, nid in net.items():
            members.setdefault(nid, []).append(pt)
        wire_pts = {pt for seg in self._split_wires() for pt in ((seg[0], seg[1]), (seg[2], seg[3]))}
        pins_in_net: dict[int, int] = {}
        for p in self.parts:
            for n in p.kind.pins:
                pins_in_net[net[p.pin(n)]] = pins_in_net.get(net[p.pin(n)], 0) + 1
        for p in self.parts:
            for n in p.kind.pins:
                pt = p.pin(n)
                if pt not in wire_pts and pins_in_net[net[pt]] < 2:     # no wire and no other pin on this node
                    issues.append(f"{p.name or p.kind.name}.{n} at {pt} is not wired")
        issues += self._dc_path_issues(net, members)
        for p in self.parts:                                  # a wire running through a part's body is a drawing error
            x0, y0, x1, y1 = p.body()
            if p.kind.name == "Ground":
                continue
            core = (x0 + 5, y0 + 1, x1 - 5, y1 - 1) if (x1 - x0) >= (y1 - y0) else (x0 + 1, y0 + 5, x1 - 1, y1 - 5)
            if core[0] >= core[2] or core[1] >= core[3]:
                continue
            for a, b, c, d in self.segments:
                seg = (min(a, c) * 8 - 0.5, min(b, d) * 8 - 0.5, max(a, c) * 8 + 0.5, max(b, d) * 8 + 0.5)
                if _overlap(core, seg) > 0:
                    issues.append(f"a wire runs through the body of {p.name or p.kind.name} near grid ({a},{b})")
                    break
        for a, b in itertools.combinations(self.segments, 2):
            if (a[0] == a[2]) != (b[0] == b[2]):                 # one vertical, one horizontal
                v, h = (a, b) if a[0] == a[2] else (b, a)
                x, y = v[0], h[1]
                inside = (min(v[1], v[3]) < y < max(v[1], v[3])) and (min(h[0], h[2]) < x < max(h[0], h[2]))
                if inside:
                    issues.append(f"wires cross at ({x},{y}) without a junction (not connected in MC9)")
        return issues

    _NO_DC = {"Capacitor", "Current Source"}     # do not provide a DC path to ground

    def _dc_path_issues(self, net, members) -> list[str]:
        """MC9 refuses to analyse circuits where a node has no DC path to ground (e.g. only capacitors)."""
        parent: dict = {}
        def find(a):
            parent.setdefault(a, a)
            while parent[a] != a:
                parent[a] = parent[parent[a]]; a = parent[a]
            return a
        for nid in members:
            find(nid)
        grounds = [net[p.pin("PinA")] for p in self.parts if p.kind.name == "Ground"]
        if not grounds:
            return ["no Ground part: every node floats"]
        for p in self.parts:
            if p.kind.name in self._NO_DC or p.kind.name == "Ground":
                continue
            ids = [net[p.pin(n)] for n in p.kind.pin_order]
            for i in ids[1:]:
                parent[find(i)] = find(ids[0])
        g = find(grounds[0])
        for gg in grounds[1:]:
            parent[find(gg)] = g
        out = []
        for nid in members:
            if find(nid) != find(grounds[0]):
                names = sorted({f"{p.name or p.kind.name}.{n}" for p in self.parts for n in p.kind.pins
                                if net.get(p.pin(n)) == nid})
                out.append("no DC path to ground at node with " + ", ".join(names))
        return out

    # ---- obstacle model + label placement ------------------------------------------------------
    def _node_boxes(self, chars: int, owners: bool = False):
        """Voltage boxes MC9 draws in dynamic analyses (design px). Unnamed net: centered on its first pin
        (by component order). Named net (Grid Text): hangs below-right of the named point. Ground: none."""
        net = self.nets()
        by_net: dict[int, list[tuple[int, int, tuple[int, int]]]] = {}
        ground_nets = {net[p.pin("PinA")] for p in self.parts if p.kind.name == "Ground"}
        for p in self.parts:
            for i, n in enumerate(p.kind.pin_order):
                pt = p.pin(n)
                by_net.setdefault(net[pt], []).append((p.index, i, pt))
        named = {net[pt]: pt for _, pt in self.nodes_named if pt in net}
        w = (12.5 * chars + 10) / 2        # design px
        h = 14.5
        boxes, own = [], []
        for nid, pins in by_net.items():
            if nid in ground_nets:
                continue
            if nid in named:
                x, y = named[nid]
                boxes.append((x * 8 - 3.5, y * 8 + 1.5, x * 8 - 3.5 + w, y * 8 + 1.5 + h))
            else:
                _, _, (x, y) = min(pins)
                boxes.append((x * 8 - w / 2, y * 8 - h / 2, x * 8 + w / 2, y * 8 + h / 2))
            own.append({self.parts[i].name or self.parts[i].kind.name for i, _, _ in pins})
        return (boxes, own) if owners else boxes

    def _name_rects(self) -> list[Rect]:
        return [(x * 8 + 0.5, y * 8 - 10.5, x * 8 + 0.5 + CHAR_W * len(t) + 1, y * 8 - 10.5 + TEXT_H + 1)
                for t, (x, y) in self.nodes_named]

    def _label_rects(self, p: Part) -> dict[str, Rect]:
        out = {}
        for key, text, off in (("part", p.name, p.part_label), ("value", p.value, p.value_label)):
            if text:
                w = CHAR_W * len(text) + 1
                x = p.at[0] * 8 + off[0] + 2
                y = p.at[1] * 8 + off[1] + 3.5
                out[key] = (x, y, x + w, y + TEXT_H)
        return out

    def auto_labels(self, mode: str = "dc", chars: int | None = None) -> None:
        """Choose PART/VALUE label offsets so they avoid bodies, wires, voltage boxes and each other.
        mode: 'dc' (short boxes), 'ac' (wide phasor boxes), 'none' (ignore voltage boxes)."""
        chars = chars or {"dc": 8, "ac": 17, "none": 0}[mode]
        boxes = (self._node_boxes(chars) if chars else []) + self._name_rects()
        wires = [_inflate((min(a, c) * 8, min(b, d) * 8, max(a, c) * 8, max(b, d) * 8), 1.5)
                 for a, b, c, d in self._split_wires()]
        bodies = [(p, _inflate(p.body(), 1.5)) for p in self.parts]
        placed: list[Rect] = []
        cb = [b for _, b in bodies] + wires
        core = (min(r[0] for r in cb) - 24, min(r[1] for r in cb), max(r[2] for r in cb) + 24, max(r[3] for r in cb))
        order = sorted(self.parts, key=lambda p: -(p.body()[2] - p.body()[0]) * (p.body()[3] - p.body()[1]))
        for p in order:
            if p.kind.name == "Ground" or p.labels_fixed or not (p.name or p.value):
                continue
            bx0, by0, bx1, by1 = p.body()
            cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
            w1 = CHAR_W * len(p.name or "") + 1
            w2 = CHAR_W * len(p.value or "") + 1
            lg = 1.0
            def stack(top_first, x_anchor, y_start, align, w1=w1, w2=w2, lg=lg):
                """Two stacked lines (value above/below name); returns {'part': rect, 'value': rect}."""
                items = (("part", w1), ("value", w2)) if top_first == "part" else (("value", w2), ("part", w1))
                rects, y = {}, y_start
                for key, w in items:
                    x = {"c": x_anchor - w / 2, "l": x_anchor, "r": x_anchor - w}[align]
                    rects[key] = (x, y, x + w, y + TEXT_H); y += TEXT_H + lg
                return rects
            hh = 2 * TEXT_H + lg
            horizontal = (bx1 - bx0) >= (by1 - by0)
            cands = []
            for gi, gap in enumerate((3.0, 8.0, 14.0, 22.0)):
                for tf in ("part", "value"):
                    for shift in (0.0, -0.5, 0.5):       # slide along the side (fraction of the body length)
                        dx = shift * (bx1 - bx0); dy = shift * (by1 - by0)
                        sides = [("above", stack(tf, cx + dx, by0 - gap - hh, "c"), 0 if horizontal else 3),
                                 ("below", stack(tf, cx + dx, by1 + gap, "c"), 1 if horizontal else 4),
                                 ("right", stack(tf, bx1 + gap, cy - hh / 2 + dy, "l"), 3 if horizontal else 0),
                                 ("left", stack(tf, bx0 - gap, cy - hh / 2 + dy, "r"), 4 if horizontal else 1)]
                        if shift == 0.0:   # long text: start/end flush with the body instead of centered
                            sides += [("above-l", stack(tf, bx0, by0 - gap - hh, "l"), 2.5),
                                      ("above-r", stack(tf, bx1, by0 - gap - hh, "r"), 2.5),
                                      ("below-l", stack(tf, bx0, by1 + gap, "l"), 3),
                                      ("below-r", stack(tf, bx1, by1 + gap, "r"), 3)]
                        for _, rects, pref in sides:
                            cands.append((rects, pref + gi * 2 + abs(shift) * 2))
            best, best_s = None, 1e18
            for rects, pref in cands:
                score = pref * 0.5
                for r in rects.values():
                    out = max(0.0, core[0] - r[0]) + max(0.0, r[2] - core[2])
                    score += 0.4 * out
                for r in rects.values():
                    score += 1000 * sum(_overlap(r, b) for b in boxes) / max(1, 1)
                    score += 1000 * sum(_overlap(r, w) for w in wires)
                    score += 1000 * sum(_overlap(r, b) for q, b in bodies)
                    score += 1000 * sum(_overlap(r, _inflate(q, 4.0)) for q in placed)     # keep labels apart
                if score < best_s:
                    best, best_s = rects, score
            if best is None:
                continue
            ox, oy = p.at[0] * 8, p.at[1] * 8
            for key, r in best.items():
                off = (round(r[0] - ox - 2), round(r[1] - oy - 3.5))
                if key == "part":
                    p.part_label = off
                else:
                    p.value_label = off
                placed.append(r)
            if best_s >= 1000:
                self.notes.append(f"{p.name or p.kind.name}: no overlap-free label position (score {best_s:.0f})")

    def audit(self, mode: str = "dc", chars: int | None = None) -> list[str]:
        """Predict visual collisions in a dynamic-analysis screenshot (mode 'dc' or 'ac').
        Voltage boxes are drawn by MC9, so overlaps with them mean: space the components further apart."""
        chars = chars or {"dc": 8, "ac": 17}[mode]
        out: list[str] = []
        boxes, owners = self._node_boxes(chars, owners=True)
        names = self._name_rects()
        labels: list[tuple[str, Rect]] = []
        for p in self.parts:
            for k, r in self._label_rects(p).items():
                labels.append((f"{p.name or p.kind.name} {k}", r))
        bodies = [(p.name or p.kind.name, _inflate(p.body(), -1.0)) for p in self.parts]
        ov = lambda a, b: _overlap(a, b) > 4          # design px^2: ignore touching edges
        for (i, a), (j, b) in itertools.combinations(list(enumerate(boxes)), 2):
            if ov(a, b):
                out.append(f"voltage boxes #{i} and #{j} overlap near grid ({a[0]/8:.0f},{a[1]/8:.0f}): space those nodes >= {int(chars*12.5/16)+2} grid units apart")
        for i, a in enumerate(boxes):
            for nm, b in labels:
                if ov(a, b):
                    out.append(f"voltage box #{i} at grid ({a[0]/8:.0f},{a[1]/8:.0f}) overlaps label '{nm}'")
            for nm, b in bodies:
                area = (a[2] - a[0]) * (a[3] - a[1])
                if nm not in owners[i] and _overlap(a, b) > 0.35 * area:
                    out.append(f"voltage box #{i} at grid ({a[0]/8:.0f},{a[1]/8:.0f}) covers body of {nm}")
        for (n1, a), (n2, b) in itertools.combinations(labels, 2):
            if ov(a, b):
                out.append(f"labels '{n1}' and '{n2}' overlap")
        for (text, _), r in zip(self.nodes_named, names):
            for nm2, b in bodies:
                if ov(r, b):
                    out.append(f"node name '{text}' overlaps body of {nm2}: name it on a free wire point instead")
            for nm, b in labels:
                if ov(r, b):
                    out.append(f"node name '{text}' overlaps label '{nm}'")
        for nm, a in labels:
            for nm2, b in bodies:
                if ov(a, b):
                    out.append(f"label '{nm}' overlaps body of {nm2}")
            for r in names:
                if ov(a, r):
                    out.append(f"label '{nm}' overlaps a node name")
        return out

    # ---- output ---------------------------------------------------------------------------------
    def bbox(self) -> tuple[int, int, int, int]:
        """Grid-unit bounding box of everything drawn (bodies, wires, labels, node names, voltage boxes)."""
        rects: list[Rect] = [p.body() for p in self.parts]
        rects += [(min(a, c) * 8, min(b, d) * 8, max(a, c) * 8, max(b, d) * 8) for a, b, c, d in self.segments]
        for p in self.parts:
            rects += list(self._label_rects(p).values())
        rects += self._name_rects() + self._node_boxes(self._box_chars)
        import math
        return (math.floor(min(r[0] for r in rects) / 8), math.floor(min(r[1] for r in rects) / 8),
                math.ceil(max(r[2] for r in rects) / 8), math.ceil(max(r[3] for r in rects) / 8))

    def _reset_analyses(self, t: cirmod.Cir) -> None:
        """The template's curves/limits refer to LR2 nodes (Ue, Ua, V1...). Replace them with valid defaults
        based on this circuit so that a first analysis works out of the box."""
        named = [n for n, _ in self.nodes_named]
        probe = named[-1] if named else next((p.name for p in self.parts if p.name and p.kind.name != "Ground"), None)
        src = next((p.name for p in self.parts if p.name and p.kind.name in
                    ("Voltage Source", "Battery", "Sine Source", "Pulse Source")), None)
        if probe is None:
            return
        spec = {"Transient": [dict(x="T", y=f"v({probe})")],
                "AC": [dict(x="F", y=f"db(v({probe}))")],
                "DC": [dict(x="DCINPUT1", y=f"v({probe})")],
                "Distortion": [dict(x="F", y=f"HARM(V({probe}))", plot=1),
                               dict(x="F", y=f"IHD(HARM(V({probe})),1000)", plot=2),
                               dict(x="F", y=f"THD(HARM(V({probe})),1000)"), dict(x="T", y=f"V({probe})", plot=4)]}
        for name, curves in spec.items():
            if t.waveform_indices(name):
                t.set_waveforms(name, curves)
        if src:
            for sec in t.sections:
                if sec.name == "Limits" and sec.get("Analysis") == "Distortion":
                    sec.set("ISource", src); sec.set("OutExpr", f"V({probe})"); sec.set("F0", "1k")
                if sec.name == "Limits" and sec.get("Analysis") == "DC":
                    sec.set("I1", src)

    CANVAS = (1665.0, 793.0)          # visible schematic canvas, screen px (2000x1100 virtual screen)

    def to_cir(self, zoom: float | None = None, margin: int = 24) -> cirmod.Cir:
        """The .cir text. The drawing is shifted to non-negative coordinates and MC9's scroll/zoom
        ([Page] SB 3 / Scale 3) are set so the whole drawing is centered in the canvas (zoom<=2: auto-fit)."""
        t = cirmod.Cir.load(self.template)
        self._reset_analyses(t)
        x0, y0, x1, y1 = self.bbox()
        w, h = (x1 - x0) * 8 + 2 * margin, (y1 - y0) * 8 + 2 * margin      # design px
        z = zoom or (2.0 if w <= self.CANVAS[0] / 2 and h <= self.CANVAS[1] / 2 else 1.0)  # MC9 snaps zoom to 2x / 1x
        if w > self.CANVAS[0] / z or h > self.CANVAS[1] / z:
            self.notes.append(f"drawing ({w}x{h} design px) is larger than MC9's canvas at {z}x zoom; it will be clipped")
        vis_w, vis_h = self.CANVAS[0] / z / 8, self.CANVAS[1] / z / 8       # grid units
        sx = max(1, round((vis_w - (x1 - x0)) / 2) - x0)                     # center by shifting (scroll can't go < 0)
        sy = max(1, round((vis_h - (y1 - y0)) / 2) - y0)
        scale = round(1 / z, 2)
        page = next(p for p in t.sections if p.name == "Page" and p.get("Index") == "0")
        page.set("SB 3", "0,0")
        page.set("Scale 3", str(scale))
        next(p for p in t.sections if p.name == "Schematic").set("Scale", str(scale))
        self.zoom = z
        m = 14                                              # screen px margin around the drawing
        self.crop_px = (round(201 + z * 8 * (x0 + sx) - m), round(102 + z * 8 * (y0 + sy) - m),
                        round(201 + z * 8 * (x1 + sx) + m), round(102 + z * 8 * (y1 + sy) + m))
        new: list[cirmod.Section] = []
        for p in self.parts:
            new.append(cirmod.Section("Comp", [f"Name={p.kind.name}", f"Grid={p.at[0]+sx},{p.at[1]+sy}", f"Rot={p.rot}"]))
            if p.name:
                new.append(cirmod.Section("Attr", [f"ONV={p.part_label[0]},{p.part_label[1]},PART,{p.name}", "Style=8192"]))
            if p.value is not None and p.kind.value_attr:
                new.append(cirmod.Section("Attr", [f"ONV={p.value_label[0]},{p.value_label[1]},{p.kind.value_attr},{p.value}", "Style=8192"]))
            for k, v in p.extra.items():                     # no Style line = hidden attribute
                new.append(cirmod.Section("Attr", [f"ONV=0,0,{k},{v}"]))
        seen = set()
        for a_, b_, c_, d_ in self._split_wires():          # MC9 joins wires only at endpoints: split T-junctions
            key = (min((a_, b_), (c_, d_)), max((a_, b_), (c_, d_)))
            if key not in seen:
                seen.add(key)
                new.append(cirmod.Section("Wire", [f"Grids={a_+sx},{b_+sy},{c_+sx},{d_+sy}"]))
        names = []
        for text, (x, y) in self.nodes_named:
            names.append(cirmod.Section("Grid Text", [f'Text="{text}"', f"Grid={x+sx},{y+sy}", "CBorder=NONE", ""]))
        have = {(s_.name, s_.get("Name")) for s_ in t.sections if s_.name in ("shapedef", "compdef")}
        defs = []                                           # definitions of parts MC9 taught us (not in the base template)
        for p in self.parts:
            for sec in p.kind.defs:
                key = (sec.name, sec.get("Name"))
                if key not in have:
                    have.add(key)
                    defs.append(copy.deepcopy(sec))
        if defs:
            j = next(k for k, s_ in enumerate(t.sections) if s_.name == "Circuit")
            t.sections[j:j] = sorted(defs, key=lambda s_: s_.name != "shapedef")
        i = max(j for j, s_ in enumerate(t.sections) if s_.name == "Circuit") + 1
        t.sections[i:i] = new + names
        main = t.sections[0]
        main.set("NLCnt", str(len(names))); main.set("TXCnt", "0")
        return t

    def build(self, name: str, labels: str = "dc", chars: int | None = None):
        """Auto-place labels, write the circuit into the sandbox and return an `mc9.Circuit`.
        chars: expected width of MC9's voltage boxes in characters (default 8 for dc, 17 for ac)."""
        from . import api
        import json
        self._box_chars = chars or {"dc": 8, "ac": 17}.get(labels, 8)
        if labels != "off":
            self.auto_labels(labels, chars)
        issues = self.check()
        if labels in ("dc", "ac"):
            issues += [f"[{labels}] {m}" for m in self.audit(labels, chars)]
        issues += self.notes
        if issues:
            import warnings
            warnings.warn("schematic problems: " + "; ".join(issues), stacklevel=2)
        self.to_cir().save(str(workspace.path(name)))
        (workspace.exchange() / f"{name}.layout.json").write_text(json.dumps({"crop": self.crop_px, "zoom": self.zoom}))
        if name in api._OPEN:
            api._OPEN.pop(name).close()
        return api.attach(name)
