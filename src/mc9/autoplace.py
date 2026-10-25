"""Automatic placement and routing for `Netlist` -> `Schematic`.

Strategy (works for the usual analog teaching circuits - filters, dividers, clippers, transistor and op-amp stages):

1. Classify nodes: ground, supply rails (DC sources to ground), the input (signal source) and the output node.
2. The *backbone* is the shortest signal path from input to output through series parts; transistors and op-amps are
   traversed base->collector / input->output. It is laid out left to right with spacing wide enough for MC9's voltage boxes.
3. Everything else hangs off backbone nodes as *branches*: parts to ground go down, parts to a rail go up (chains of series
   parts are stacked). A part joining two backbone nodes (feedback) is a *bridge*.
4. Ground and rails are drawn as buses; sources sit at the ends. If a drawing would cross wires, the offending net falls
   back to *named labels* (MC9 treats equally named nodes as one net), so the result is always electrically correct.
5. The result is checked with `Schematic.check()/audit()` and re-spaced if boxes or labels would collide.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from . import catalog
from .netlist import GROUND, Netlist, NPart
from .schematic import Part, Schematic

COL = 8          # horizontal room for one hanging branch (grid units)
STUB = 3         # wire between a node and the first part of a branch
SOURCES = ("Voltage Source", "Battery")


def _signal_value(v: str | None) -> bool:
    t = (v or "").lower().split()
    return "sin" in t or "pulse" in (v or "").lower() or "ac" in t


@dataclass
class Options:
    mode: str = "dc"                       # "dc" | "ac": how much room MC9's voltage boxes need
    gap: int | None = None                 # minimum backbone wire length (grid); default by mode
    input: str | None = None               # input node (default: node of the first signal source)
    output: str | None = None              # output node (default: the node farthest from the input)
    label_nets: set = field(default_factory=set)
    ground_labels: bool = False            # a Ground symbol on every ground pin instead of a bus
    rails_as_labels: bool = False


class _Run:
    def __init__(self, nl: Netlist, o: Options, gap: int):
        self.nl, self.o, self.gap = nl, o, gap
        self.sch = Schematic()
        self.by_net: dict[str, list[tuple[NPart, str]]] = {}
        for p in nl.parts:
            for pin, net in p.nets.items():
                self.by_net.setdefault(net, []).append((p, pin))
        self.placed: dict[str, Part] = {}
        self.wires: list[tuple[tuple, tuple, str]] = []
        self.net_pt: dict[str, tuple[int, int]] = {}
        self.ground_drops: list[tuple[int, int]] = []
        self.ground_up: list[tuple[int, int]] = []              # ground symbols that must point up (end of an upward stub)
        self.rail_drops: dict[str, list[tuple[int, int]]] = {}
        self.stubs: list[tuple[str, tuple[int, int]]] = []       # (net, point) pairs connected by name only
        self.auto = 0
        self.notes: list[str] = []
        self.rail_src: dict[str, NPart] = {}
        self.bridges_labeled: set[str] = set()
        self.bb_nets: set[str] = set()
        self.anchor_nets: set[str] = set()

    # ---- small helpers ------------------------------------------------------------------------
    def gnd(self, n: str) -> bool:
        return n in GROUND

    def rail(self, n: str) -> bool:
        return n in self.rail_src

    def W(self, a, b, net: str) -> None:
        a, b = (int(a[0]), int(a[1])), (int(b[0]), int(b[1]))
        if a == b:
            return
        if a[0] != b[0] and a[1] != b[1]:               # make every wire axis aligned
            self.W(a, (b[0], a[1]), net); self.W((b[0], a[1]), b, net)
            return
        self.sch.wire(a, b)
        self.wires.append((a, b, net))

    def mark(self, net: str, pt) -> None:
        self.net_pt.setdefault(net, (int(pt[0]), int(pt[1])))

    def rot_for(self, kind: catalog.Kind, first: str, second: str, axis: str) -> int:
        """Rotation putting pin `first` before `second` along x (left->right) or y (top->bottom)."""
        for rot in ((0, 2) if axis == "x" else (1, 3)):
            a = catalog.transform(*kind.pins[first], rot)
            b = catalog.transform(*kind.pins[second], rot)
            if (a[0] < b[0]) if axis == "x" else (a[1] < b[1]):
                return rot
        return 0

    def add(self, p: NPart, at, rot: int) -> Part:
        sp = self.sch.add(p.kind.name, p.name, p.value, at=at, rot=rot, **p.extra)
        self.placed[p.name] = sp
        return sp

    def pin_of(self, p: NPart, net: str, skip: str | None = None) -> str:
        return next(pin for pin, n in p.nets.items() if n == net and pin != skip)

    def label_name(self, net: str) -> str:
        if net.startswith("_") or net in GROUND:
            self.auto += 1
            return f"n{self.auto}"
        return net

    def label_pt(self, net: str, pt) -> None:
        self.stubs.append((net, (int(pt[0]), int(pt[1]))))

    # ---- classification -----------------------------------------------------------------------
    def classify(self) -> None:
        parts = self.nl.parts
        grounded = [p for p in parts if p.kind.name in SOURCES and any(self.gnd(n) for n in p.nets.values())]
        sig = [p for p in grounded if _signal_value(p.value)]
        active = any(p.kind.name in ("NPN", "PNP", "Opamp", "NMOS") for p in parts)
        self.src = None
        if self.o.input:
            self.src = next((p for p in grounded if self.o.input in p.nets.values()), None)
        elif sig:
            self.src = sig[0]
        elif grounded and not active:
            self.src = grounded[0]
        self.supplies = [p for p in grounded if p is not self.src]
        for p in self.supplies:
            net = next(n for n in p.nets.values() if not self.gnd(n))
            self.rail_src[net] = p
        self.input_net = self.o.input or (next((n for n in self.src.nets.values() if not self.gnd(n)), None) if self.src else None)
        if self.input_net is None:
            raise ValueError("no input: add a signal source (sin/pulse/AC) between a node and 0, or pass input='node'")

    def edges(self):
        """Traversable (part, enter_pin, exit_pin) per node, excluding ground/rail nodes and source/supply parts."""
        out: dict[str, list[tuple[NPart, str, str]]] = {}
        for p in self.nl.parts:
            if p is self.src or p in self.supplies:
                continue
            k = p.kind.name
            pairs: list[tuple[str, str]] = []
            if p.two_terminal:
                a, b = list(p.nets)
                pairs = [(a, b), (b, a)]
            elif k in ("NPN", "PNP"):
                pairs = [("Base", "Collector")]
            elif k == "NMOS":
                pairs = [("Gate", "Drain")]
            elif k == "Opamp":
                pairs = [("Plus input", "Output"), ("Minus input", "Output")]
            for ein, eout in pairs:
                na, nb = p.nets[ein], p.nets[eout]
                if self.gnd(na) or self.gnd(nb) or self.rail(na) or self.rail(nb) or na == nb:
                    continue
                out.setdefault(na, []).append((p, ein, eout))
        for lst in out.values():                      # active devices first: they, not feedback parts, form the path
            lst.sort(key=lambda st: st[0].two_terminal)
        return out

    def find_backbone(self) -> list[tuple[NPart, str, str]]:
        e = self.edges()
        prev: dict[str, tuple[str, tuple]] = {}
        order = [self.input_net]
        q = deque([self.input_net])
        seen = {self.input_net}
        while q:
            n = q.popleft()
            for step in e.get(n, []):
                m = step[0].nets[step[2]]
                if m not in seen:
                    seen.add(m); prev[m] = (n, step); order.append(m); q.append(m)
        controls = {n for p in self.nl.parts for pin, n in p.nets.items()
                    if pin in ("Base", "Gate", "Plus input", "Minus input")}      # feedback nodes are never "the output"
        cands = [n for n in order[1:] if n not in controls]
        target = self.o.output or (cands[-1] if cands else (order[-1] if len(order) > 1 else None))
        if target is None or target not in prev:
            return []
        path, n = [], target
        while n != self.input_net:
            n, step = prev[n]
            path.append(step)
        path.reverse()
        self.output_net = target
        return path

    @staticmethod
    def colw(items) -> int:
        """Horizontal room for hanging branches: wide enough for the labels each part carries."""
        w = COL
        for p, _pin in items:
            chars = max(len(p.name or ""), len(p.value or ""))
            w = max(w, int(chars * 7 / 8 + 0.999) + 5)
        return w

    # ---- branches -----------------------------------------------------------------------------
    def branch_items(self, net: str) -> list[tuple[NPart, str]]:
        return [(p, pin) for p, pin in self.by_net.get(net, [])
                if p.name not in self.placed and p.two_terminal and p is not self.src and p not in self.supplies
                and not any(n in (self.bb_nets | self.anchor_nets) and n != net for n in p.nets.values())]  # those are bridges

    def direction_of(self, p: NPart, net: str) -> str:
        o = p.nets[next(pin for pin in p.nets if p.nets[pin] != net)] if len({*p.nets.values()}) > 1 else net
        return "up" if self.rail(o) else "down"

    def hang(self, net: str, anchors: list[tuple[int, int]], direction: str | None = None) -> None:
        """Hang the unplaced parts of `net` below/above anchor points that lie on a wire of that net."""
        items = self.branch_items(net)
        if not items:
            return
        groups = {"up": [], "down": []}
        for p, pin in items:
            groups[direction or self.direction_of(p, net)].append((p, pin))
        for d, lst in groups.items():
            for i, (p, _pin) in enumerate(lst):
                ax, ay = anchors[min(i, len(anchors) - 1)] if len(anchors) >= len(lst) else anchors[0]
                if len(anchors) < len(lst):
                    ax += round((i - (len(lst) - 1) / 2) * self.colw(lst))
                if p.name in self.placed:
                    continue
                self.chain(p, net, (ax, ay), d)

    def chain(self, p: NPart, net: str, node: tuple[int, int], d: str) -> None:
        x, y = node
        near = self.pin_of(p, net)
        far = next(pin for pin in p.nets if pin != near)
        sgn = 1 if d == "down" else -1
        y_near = y + sgn * STUB
        rot = self.rot_for(p.kind, near, far, "y") if d == "down" else self.rot_for(p.kind, far, near, "y")
        off = catalog.transform(*p.kind.pins[near], rot)
        part = self.add(p, (x - off[0], y_near - off[1]), rot)
        self.W((x, y), (x, y_near), net)
        far_pt = part.pin(far)
        self.mark(net, (x, y + sgn))
        fnet = p.nets[far]
        if self.gnd(fnet):
            self.ground_drops.append(far_pt)
        elif self.rail(fnet):
            self.rail_drops.setdefault(fnet, []).append(far_pt)
        else:
            self.mark(fnet, far_pt)
            self.hang(fnet, [far_pt], d)
            # net continues nowhere else: remember a point for labels
            if self.branch_items(fnet) == [] and len(self.by_net.get(fnet, [])) <= 1:
                self.notes.append(f"node {fnet} is connected to a single pin")

    # ---- main layout --------------------------------------------------------------------------
    def layout(self) -> None:
        self.classify()
        path = self.find_backbone()
        if not path:
            raise ValueError("no signal path between the input and the output node; set input=/output= or check the netlist")
        self.bb_nets = {self.input_net} | {p.nets[eout] for p, _, eout in path}
        for p, ein, eout in path:                      # nets of side pins (emitter, 2nd op-amp input) get their own anchor
            if not p.two_terminal:
                self.anchor_nets |= {n for pin, n in p.nets.items() if pin not in (ein, eout, "VCC", "VEE")
                                     and not self.gnd(n) and not self.rail(n)}
        y = 0
        xs = 0
        srcp = self.add(self.src, (xs, y + 6), 3)             # vertical source: Plus up
        plus = srcp.pin("Plus")
        self.ground_drops.append(srcp.pin("Minus"))
        prev, row_y = plus, y
        self.mark(self.input_net, (prev[0] + 2, prev[1]))
        for _i, (p, ein, eout) in enumerate(path):
            net_in, net_out = p.nets[ein], p.nets[eout]
            ups = [it for it in self.branch_items(net_in) if self.direction_of(it[0], net_in) == "up"]
            downs = [it for it in self.branch_items(net_in) if self.direction_of(it[0], net_in) == "down"]
            cw = self.colw(ups + downs)
            gap = max(self.gap, cw * max(len(ups), len(downs), 1) + 2)
            if p.kind.name in ("NPN", "PNP", "NMOS", "Opamp"):
                rot = 0
            else:
                rot = self.rot_for(p.kind, ein, eout, "x")
            off = catalog.transform(*p.kind.pins[ein], rot)
            enter = (prev[0] + gap, row_y)
            part = self.add(p, (enter[0] - off[0], enter[1] - off[1]), rot)
            self.W(prev, enter, net_in)
            ax = prev[0] + gap // 2
            anchors = [(ax, row_y)]
            if len(ups) > 1 or len(downs) > 1:
                n = max(len(ups), len(downs))
                anchors = [(round(ax + (k - (n - 1) / 2) * cw), row_y) for k in range(n)]
            self.mark(net_in, (prev[0] + 2, row_y)) if net_in not in self.net_pt else None
            self.hang(net_in, anchors)
            exit_pt = part.pin(eout)
            row_y = exit_pt[1]
            self.side_pins(p, part, ein, eout)
            prev = exit_pt
            self.mark(net_out, (prev[0] + 2, row_y))
        # output tail
        ups = [it for it in self.branch_items(self.output_net) if self.direction_of(it[0], self.output_net) == "up"]
        downs = [it for it in self.branch_items(self.output_net) if self.direction_of(it[0], self.output_net) == "down"]
        cw = self.colw(ups + downs)
        gap = max(self.gap, cw * max(len(ups), len(downs), 1) + 2)
        n = max(len(ups), len(downs), 1)
        anchors = [(round(prev[0] + gap // 2 + (k - (n - 1) / 2) * cw), row_y) for k in range(n)]
        has_branches = bool(ups or downs)
        end = (max(a[0] for a in anchors) if has_branches else prev[0] + 6, row_y)   # no dangling wire past the last branch
        self.W(prev, end, self.output_net)
        self.hang(self.output_net, anchors)
        self.bridges(path, row_y)
        self.rail_buses()
        self.leftovers()
        self.ground_bus()

    def side_pins(self, p: NPart, part: Part, ein: str, eout: str) -> None:
        """Pins of multi-pin parts that are not on the backbone: emitter/source, op-amp second input and supplies."""
        k = p.kind.name
        if k in ("NPN", "PNP", "NMOS"):
            pin = "Emitter" if k != "NMOS" else "Source"
            pt = part.pin(pin)
            net = p.nets[pin]
            d = "down" if (pt[1] > part.pin(ein)[1]) else "up"
            self.route_pin(net, pt, d)
            if k == "NMOS":
                bpt = part.pin("Body"); bnet = p.nets["Body"]
                if bnet != net:
                    self.route_pin(bnet, (bpt[0] + 0, bpt[1]), "down", stub_x=2)
        elif k == "Opamp":
            other = "Plus input" if ein == "Minus input" else "Minus input"
            pt = part.pin(other)
            net = p.nets[other]
            if self.gnd(net):
                end = (pt[0] - 3, pt[1])
                self.W(pt, end, net)
                self.ground_drops.append(end)
            else:
                end = (pt[0] - 4, pt[1])
                self.W(pt, end, net)
                self.mark(net, (end[0], end[1]))
                self.hang(net, [end], "down")
            for pin, d in (("VCC", "up"), ("VEE", "down")):
                net = p.nets[pin]
                pt = part.pin(pin)
                end = (pt[0], pt[1] + (-STUB if d == "up" else STUB))
                self.W(pt, end, net)
                if self.rail(net) and d == "up" and not self.o.rails_as_labels:
                    self.rail_drops.setdefault(net, []).append(end)
                elif self.gnd(net):
                    self.ground_drops.append(end)
                else:
                    self.label_pt(net, end)

    def route_pin(self, net: str, pt, d: str, stub_x: int = 0) -> None:
        if self.gnd(net):
            self.ground_drops.append(pt)
        elif self.rail(net):
            self.rail_drops.setdefault(net, []).append(pt)
        else:
            self.mark(net, pt)
            self.hang(net, [pt], d)

    def bridges(self, path, row_y: int) -> None:
        """Parts joining two nets that already have points (feedback): placed above the backbone with labelled stubs."""
        todo = [p for p in self.nl.parts if p.name not in self.placed and p.two_terminal and p is not self.src
                and p not in self.supplies and all(n in self.net_pt for n in p.nets.values())]
        top = min([w[0][1] for w in self.wires] + [w[1][1] for w in self.wires] + [row_y]) - 8
        for i, p in enumerate(todo):
            a, b = list(p.nets.values())
            xa, xb = self.net_pt[a][0], self.net_pt[b][0]
            cx = (xa + xb) // 2
            ytop = top - 8 * i
            pa, pb = list(p.nets)[0], list(p.nets)[1]
            na, nb = p.nets[pa], p.nets[pb]
            left_first = self.net_pt[na][0] <= self.net_pt[nb][0]
            first, second = (pa, pb) if left_first else (pb, pa)
            rot = self.rot_for(p.kind, first, second, "x")
            off = catalog.transform(*p.kind.pins[first], rot)
            x1 = cx - 3
            part = self.add(p, (x1 - off[0], ytop - off[1]), rot)
            direct = p.nets[first] not in self.o.label_nets and p.nets[second] not in self.o.label_nets
            for pin in (first, second):
                net = p.nets[pin]; pt = part.pin(pin); anchor = self.net_pt[net]
                if direct:
                    self.W(pt, (anchor[0], pt[1]), net)
                    self.W((anchor[0], pt[1]), anchor, net)
                else:
                    end = (pt[0] + (-3 if pin == first else 3), pt[1])
                    self.W(pt, end, net)
                    self.label_pt(net, end)
                    self.label_pt(net, anchor)

    def leftovers(self) -> None:
        """Anything still unplaced (supplies for label rails, odd parts) goes into a free row, connected by labels."""
        free = [p for p in self.nl.parts if p.name not in self.placed]
        xs = [w[0][0] for w in self.wires] + [w[1][0] for w in self.wires]
        x = (max(xs) if xs else 0) + 16
        for p in free:
            if p.kind.name in SOURCES:
                plus = next(pin for pin in p.nets if pin in ("Plus",))
                minus = "Minus"
                part = self.add(p, (x, 6), 3)
                pp = part.pin("Plus"); mp = part.pin("Minus")
                end = (pp[0], pp[1] - STUB)
                self.W(pp, end, p.nets[plus])
                net = p.nets[plus]
                if self.gnd(net):
                    self.ground_up.append(end)
                else:
                    self.label_pt(net, end)
                mnet = p.nets[minus]
                if self.gnd(mnet):
                    self.ground_drops.append(mp)
                else:
                    end2 = (mp[0], mp[1] + STUB)
                    self.W(mp, end2, mnet)
                    self.label_pt(mnet, end2)
                x += 12
            else:
                self.notes.append(f"{p.name}: could not be placed automatically; connect it by node name")

    def rail_buses(self) -> None:
        """First up-rail as a bus with its source at the right end; further rails by labels."""
        used = []
        for net, drops in list(self.rail_drops.items()):
            src = self.rail_src.get(net)
            if self.o.rails_as_labels or net in self.o.label_nets or (used and True):
                for pt in drops:
                    end = (pt[0], pt[1] - STUB)
                    self.W(pt, end, net)
                    self.label_pt(net, end)
                if src and src.name not in self.placed:
                    pass
                continue
            used.append(net)
            ytop = min(pt[1] for pt in drops) - 3
            xmin, xmax = min(pt[0] for pt in drops), max(pt[0] for pt in drops)
            for pt in drops:
                self.W(pt, (pt[0], ytop), net)
            xs = xmax
            right = max([w[0][0] for w in self.wires] + [w[1][0] for w in self.wires] + [xmax])
            if src is not None and src.name not in self.placed:
                xs = max(xmax + 10, right + 8)       # beyond the whole circuit: its drop to ground must not cut through parts
                part = self.add(src, (xs, ytop + 6), 3)
                plus_pt = part.pin("Plus")
                if self.gnd(src.nets["Plus"]):                       # negative rail: source upside down
                    self.sch.parts.remove(part); self.placed.pop(src.name)
                    part = self.add(src, (xs, ytop), 1)
                    plus_pt, minus_pt = part.pin("Plus"), part.pin("Minus")
                    self.W((xmax, ytop), (xs, ytop), net)
                else:
                    self.W((xmax, ytop), plus_pt, net)
                    minus_pt = part.pin("Minus")
                self.ground_drops.append(minus_pt)
            self.W((xmin, ytop), (xs, ytop), net)
            self.mark(net, (xmin, ytop))

    def ground_bus(self) -> None:
        for pt in self.ground_up:
            self.sch.add("GND", None, at=pt, rot=3)
        if not self.ground_drops:
            return
        if self.o.ground_labels or "0" in self.o.label_nets:
            for pt in self.ground_drops:
                self.sch.add("GND", None, at=pt)
            return
        ybot = max(pt[1] for pt in self.ground_drops) + 3
        xs = [pt[0] for pt in self.ground_drops]
        for pt in self.ground_drops:
            self.W(pt, (pt[0], ybot), "0")
        self.W((min(xs), ybot), (max(xs), ybot), "0")
        self.sch.add("GND", None, at=(max(xs), ybot))

    # ---- finishing ----------------------------------------------------------------------------
    def finish(self) -> Schematic:
        for net in self.nl.nodes():
            if self.gnd(net) or net.startswith("_") or net not in self.net_pt:
                continue
            self.sch.node(net, self.net_pt[net])
        done: set[str] = set()
        for net, pt in self.stubs:                        # name-connected stubs: every group needs the same label
            nm = self.label_name(net)
            self.sch.node(nm, pt)
            done.add(net)
        self.sch.notes += self.notes
        return self.sch

    def crossings(self) -> list[tuple[str, str]]:
        """Pairs of nets whose recorded wires cross without sharing an endpoint."""
        out = []
        for i, (a1, a2, n1) in enumerate(self.wires):
            for b1, b2, n2 in self.wires[i + 1:]:
                if n1 == n2 or (a1[0] == a2[0]) == (b1[0] == b2[0]):
                    continue
                v, h = ((a1, a2), (b1, b2)) if a1[0] == a2[0] else ((b1, b2), (a1, a2))
                x, y = v[0][0], h[0][1]
                if min(v[0][1], v[1][1]) < y < max(v[0][1], v[1][1]) and min(h[0][0], h[1][0]) < x < max(h[0][0], h[1][0]):
                    out.append((n1, n2))
        return out


def place(nl: Netlist, mode: str = "dc", gap: int | None = None, input: str | None = None, output: str | None = None,
          rails_as_labels: bool = False, ground_labels: bool = False, max_tries: int = 8) -> Schematic:
    """Place and route a netlist. Returns a `Schematic` (call `.build(name)`); `.notes` lists anything unusual."""
    o = Options(mode=mode, gap=gap, input=input, output=output, rails_as_labels=rails_as_labels, ground_labels=ground_labels)
    g = gap or (8 if mode == "dc" else 14)
    last = None
    for _ in range(max_tries):
        r = _Run(nl, o, g)
        r.layout()
        crossed = r.crossings()
        if crossed:                                        # cheapest fix first: ground per pin, then rails, then bridges
            nets = {n for pair in crossed for n in pair}
            if "0" in nets and not o.ground_labels:
                o.ground_labels = True
            elif any(r.rail(n) for n in nets) and not o.rails_as_labels:
                o.rails_as_labels = True
            else:
                o.label_nets |= {n for n in nets if n != "0"}
            last = r
            continue
        sch = r.finish()
        sch.auto_labels(mode)
        issues = sch.audit(mode)
        boxes = [m for m in issues if "voltage box" in m or "overlap" in m]
        if boxes and g < 26:
            g += 4
            last = r
            continue
        return sch
    sch = (last or r).finish()
    sch.notes.append("auto-placement did not converge to a collision-free drawing; check the audit messages")
    return sch
