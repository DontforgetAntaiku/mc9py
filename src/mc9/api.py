"""Public scripting API.

    import mc9
    with mc9.open("lab/lr2.cir") as c:             # copied into the sandbox; the original is never touched
        c.set("R1", "RESISTANCE", "300")
        r = c.ac(1, 2e7, points=401, curves=["db(v(Ua)/v(Ue))", "ph(v(Ua)/v(Ue))"])
        f_lo, f_hi = r.cross("db(v(Ua)/v(Ue))", r.peak("db(v(Ua)/v(Ue))")[1] - 3)
        c.cursors(f_lo, f_hi)                       # MC9's own cursors + cursor table
        c.shot("ac.png")                            # native MC9 pixels, tight crop
"""
from __future__ import annotations

import atexit
import bisect
import hashlib
import math
import shutil
import warnings
from pathlib import Path
from typing import Iterable, Sequence

from . import catalog
from . import cir as cirmod
from . import results as resmod
from . import ui, workspace
from .config import config
from .stepping import Step

_ANALYSES = ("transient", "ac", "dc", "distortion")
_LIMIT_NAME = {"transient": "Transient", "ac": "AC", "dc": "DC", "distortion": "Distortion",
               "dynamic_ac": "DynamicAC", "dynamic_dc": "DynamicDC"}


def _num(v) -> str:
    """Python number -> MC9 text (strings pass through, so '4.7k' works)."""
    return v if isinstance(v, str) else repr(float(v)) if not float(v).is_integer() else str(int(v))


# ----------------------------------------------------------------------------------------------
class Run:
    """One run's data: x = first column. Helper methods interpolate (log-x for wide AC sweeps)."""

    def __init__(self, analysis: str, columns: list[str], units: list[str], rows: list[list[float]], label: str = ""):
        self.analysis, self.columns, self.units, self.label = analysis, list(columns), units, label
        self._cols = {c: [r[i] for r in rows] for i, c in enumerate(columns)}

    @property
    def x(self) -> list[float]:
        return self._cols[self.columns[0]]

    def __getitem__(self, col: str) -> list[float]:
        try:
            return self._cols[col]
        except KeyError:
            lower = {c.lower(): c for c in self.columns}
            if col.lower() in lower:
                return self._cols[lower[col.lower()]]
            raise KeyError(f"no column {col!r}; have {self.columns}") from None

    def __len__(self) -> int:
        return len(self.x)

    @property
    def params(self) -> dict[str, float | str]:
        """What this stepped run used: ``{"Temperature": 25.0, "R1": 1000.0}`` (empty when nothing was stepped)."""
        out: dict[str, float | str] = {}
        for tok in self.label.split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                val = resmod.parse_value(v)
                out[k] = v if val is None else val
        return out

    def _log_x(self) -> bool:
        x = self.x
        return self.analysis == "ac" and min(x) > 0 and max(x) / min(x) > 50

    def value_at(self, col: str, x: float) -> float:
        """Interpolated y at x."""
        xs, ys = self.x, self[col]
        i = bisect.bisect_left(xs, x)
        if i == 0:
            return ys[0]
        if i >= len(xs):
            return ys[-1]
        t = (math.log(x / xs[i - 1]) / math.log(xs[i] / xs[i - 1])) if self._log_x() \
            else (x - xs[i - 1]) / (xs[i] - xs[i - 1])
        return ys[i - 1] + t * (ys[i] - ys[i - 1])

    def cross(self, col: str, level: float, edge: str | None = None) -> list[float]:
        """x values where the curve crosses `level` (interpolated). edge: 'rising' | 'falling' | None."""
        xs, ys, out = self.x, self[col], []
        for i in range(1, len(xs)):
            a, b = ys[i - 1] - level, ys[i] - level
            if a != a or b != b or a == b or a * b > 0:
                continue
            if (edge == "rising" and not b > a) or (edge == "falling" and not b < a):
                continue
            t = -a / (b - a)
            out.append(xs[i - 1] * (xs[i] / xs[i - 1]) ** t if self._log_x() else xs[i - 1] + t * (xs[i] - xs[i - 1]))
        return out

    def _window(self, col, xmin, xmax):
        return [(x, y) for x, y in zip(self.x, self[col]) if y == y
                and (xmin is None or x >= xmin) and (xmax is None or x <= xmax)]

    def peak(self, col: str, xmin: float | None = None, xmax: float | None = None) -> tuple[float, float]:
        """(x, y) of the maximum within [xmin, xmax]."""
        return max(self._window(col, xmin, xmax), key=lambda p: p[1])

    def trough(self, col: str, xmin: float | None = None, xmax: float | None = None) -> tuple[float, float]:
        return min(self._window(col, xmin, xmax), key=lambda p: p[1])

    def amplitude(self, col: str, xmin: float | None = None, xmax: float | None = None) -> float:
        """(max - min) / 2 inside the window (sine amplitude in steady state)."""
        ys = [y for _, y in self._window(col, xmin, xmax)]
        return (max(ys) - min(ys)) / 2

    def mean(self, col: str, xmin: float | None = None, xmax: float | None = None) -> float:
        ys = [y for _, y in self._window(col, xmin, xmax)]
        return sum(ys) / len(ys)

    def to_csv(self, path: str) -> None:
        with open(path, "w") as f:
            f.write(",".join(self.columns) + "\n")
            for i in range(len(self)):
                f.write(",".join(repr(self._cols[c][i]) for c in self.columns) + "\n")

    def __repr__(self) -> str:
        return f"Run({self.analysis}, {len(self)} rows, columns={self.columns}{', ' + self.label if self.label else ''})"


class Result:
    """Numeric output of one analysis. Behaves like its first run; stepped runs are in `.runs`."""

    def __init__(self, analysis: str, path: str):
        self.analysis, self.path = analysis, path
        tables = resmod.parse_waveforms(resmod.read_text(path))
        if not tables:
            raise RuntimeError(f"no 'Waveform Values' in {path}: numeric output disabled, no curves "
                               "defined, or the run failed (see c.shot('debug.png', 'window'))")
        self.runs: list[Run] = []
        cur: dict | None = None
        for t in tables:
            if cur is not None and t["columns"] == cur["columns"] and len(self.runs) >= 0 and t["columns"][1:] \
                    and cur.get("closed", True):
                self.runs.append(self._mk(cur)); cur = None
            if cur is not None and len(t["rows"]) == len(cur["rows"]) and t["columns"][0] == cur["columns"][0] \
                    and [r[0] for r in t["rows"]] == [r[0] for r in cur["rows"]]:
                for j, c in enumerate(t["columns"][1:], 1):   # extra page of the same run: add columns
                    cur["columns"].append(c)
                    for r0, r1 in zip(cur["rows"], t["rows"]):
                        r0.append(r1[j])
                continue
            if cur is not None:
                self.runs.append(self._mk(cur))
            cur = {"columns": list(t["columns"]), "units": t["units"], "rows": [list(r) for r in t["rows"]],
                   "label": t.get("label", "")}
        if cur is not None:
            self.runs.append(self._mk(cur))

    def _mk(self, d: dict) -> Run:
        return Run(self.analysis, d["columns"], d["units"], d["rows"], d["label"])

    def select(self, **params) -> list[Run]:
        """Stepped runs whose parameters match, e.g. ``result.select(R1=2000)`` (numbers compare with 0.1 % tolerance)."""
        def same(a, b):
            return abs(a - b) <= 1e-3 * max(abs(a), abs(b), 1e-30) if isinstance(a, float) and isinstance(b, float) else a == b
        return [r for r in self.runs if all(k in r.params and same(r.params[k], float(v) if not isinstance(v, str) else v)
                                            for k, v in params.items())]

    # first run delegates
    @property
    def columns(self) -> list[str]:
        return self.runs[0].columns

    @property
    def x(self) -> list[float]:
        return self.runs[0].x

    def __getitem__(self, col: str) -> list[float]:
        return self.runs[0][col]

    def __len__(self) -> int:
        return len(self.runs[0])

    def __getattr__(self, name: str):
        if name in ("value_at", "cross", "peak", "trough", "amplitude", "mean", "to_csv", "units"):
            return getattr(self.runs[0], name)
        raise AttributeError(name)

    def __repr__(self) -> str:
        return f"Result({self.analysis}, {len(self.runs)} run(s), {len(self)} rows, columns={self.columns})"


class OP:
    """DC operating point: node voltages and per-device values (gm, IC, power, ...)."""

    def __init__(self, path: str):
        d = resmod.parse_op(resmod.read_text(path))
        self.nodes: dict[str, float] = d["nodes"]
        self.devices: dict[str, dict[str, float]] = d["devices"]

    def v(self, node: str) -> float:
        """Node voltage by name or number (case-insensitive)."""
        for k, val in self.nodes.items():
            if k.lower() == str(node).lower():
                return val
        raise KeyError(f"no node {node!r}; have {list(self.nodes)}")

    def __getitem__(self, device: str) -> dict[str, float]:
        for k, val in self.devices.items():
            if k.lower() == device.lower():
                return val
        raise KeyError(f"no device {device!r}; have {list(self.devices)}")

    def __repr__(self) -> str:
        return f"OP(nodes={self.nodes}, devices={list(self.devices)})"


# ----------------------------------------------------------------------------------------------
class Circuit:
    def __init__(self, name: str):
        self.name = name
        self.path = workspace.path(name)
        self._cir = cirmod.Cir.load(str(self.path))
        self._dirty = True  # the first run must write the numeric-output flags
        self._ui: ui.MC9 | None = None
        self._hash: str | None = None
        self.last: Result | None = None
        self._steps: dict[str, list[Step]] = {}
        self._nested = True

    # ---- stepping -----------------------------------------------------------------------------
    def step(self, what: str, start, stop=None, step=None, *, param: str | None = None, method: str | None = None,
             kind: str = "component", enabled: bool = True, analysis: str | Sequence[str] | None = None) -> None:
        """Add a stepped variable; every later analysis runs once per value (the runs are ``result.runs``).

        ``c.step("R1", "1k", "3k", "1k")``                      R1 = 1k, 2k, 3k (linear)
        ``c.step("R1", 1e3, 1e5, 10, method="log")``            multiply by 10 each run
        ``c.step("C1", "1n,10n,100n")``                         a list of values
        ``c.step("BF420", 100, 400, 100, param="BF", kind="model")``   a model parameter
        Up to 20 variables; they change as nested loops (default) or all together (``stepping_mode(False)``).
        ``analysis=`` limits it to "transient"/"ac"/"dc"/"distortion" (default: all four).
        """
        if method is None:
            method = "list" if stop is None and "," in str(start) else "linear"
        text = lambda v: "" if v is None else _num(v)  # noqa: E731
        st = Step(what, text(start), text(stop), text(step), param, method, kind, enabled)
        for a in ([analysis] if isinstance(analysis, str) else analysis or _ANALYSES):
            self._steps.setdefault(a.lower(), []).append(st)
        self._dirty = True

    def clear_steps(self) -> None:
        """Switch stepping off for the following runs."""
        for a in self._steps:
            self._steps[a] = []
        self._dirty = True

    def stepping_mode(self, nested: bool = True) -> None:
        """``True``: every combination (nested loops); ``False``: all variables change simultaneously."""
        self._nested = nested
        self._dirty = True

    def optimize(self, params: dict, goals: Sequence, analysis: str = "ac", method: str = "standard",
                 timeout: float = 600) -> dict:
        """Let MC9's Powell optimizer tune up to 4 parts to up to 4 goals (native engine); the result is applied to the circuit.

        ``c.optimize({"R1": (50, 1e3), "C1": (0.5e-9, 2e-9)}, [("equals", "Y_Level(db(v(out)),1,1,1e6)", -3)], analysis="ac")``
        Goal kinds: "equals" (value is the target), "minimize", "maximize" (no target). Part values are searched between the limits
        (an optional third number is the step). Returns ``{"params": {"R1": {"start": .., "value": ..}}, "goals": [...]}``.
        """
        analysis = analysis.lower()
        kinds = {"equals": "Equates", "equate": "Equates", "minimize": "Minimizes", "maximize": "Maximizes"}
        plist = [(n, _num(r[0]), _num(r[1]), _num(r[2] if len(r) > 2 else (r[1] - r[0]) / 10 if not isinstance(r[0], str) else r[0]))
                 for n, r in params.items()]
        glist = []
        for g in goals:
            kind, func = kinds[g[0].lower()], g[1]
            glist.append((kind, func, _num(g[2]) if len(g) > 2 and g[2] is not None and kind == "Equates" else None))
        if not 1 <= len(plist) <= 4 or not 1 <= len(glist) <= 4:
            raise ValueError("the optimizer takes 1-4 parameters and 1-4 goals")
        self._cir.set_optimize(_LIMIT_NAME[analysis], plist, glist, "Standard_Powell" if method == "standard" else "Stepping_Powell")
        self._dirty = True
        m = self._session()
        self._to_schematic(m)
        res = m.optimize(analysis, timeout)
        for name, v in res["params"].items():                       # keep the file in step with what MC9 now holds
            val = resmod.parse_value(v["value"].split()[0]) if v["value"].strip() else None
            if val is not None and name in {c["attrs"].get("PART") for c in self._cir.components()}:
                self.set(name, catalog.VALUE_ATTR.get(self._cir.find_part(name)["type"], "VALUE"), val)
        return res

    # ---- models, tolerances, Monte Carlo -------------------------------------------------------
    def model(self, *lines: str) -> None:
        """Add netlist text to the circuit (MC9's *Text* page): ``c.model(".MODEL BF420X NPN (BF=300 IS=1E-14)")``."""
        self._cir.add_text(list(lines))
        self._dirty = True

    _TOL_MODEL = {"Resistor": ("RES", "R"), "Capacitor": ("CAP", "C"), "Inductor": ("IND", "L")}

    def tolerance(self, part: str, lot: str | float | None = None, dev: str | float | None = None) -> None:
        """Give a resistor/capacitor/inductor a tolerance for Monte Carlo: ``c.tolerance("R1", lot="5%")``.

        ``lot``: all parts of that lot move together; ``dev``: each part varies on its own (percent, e.g. ``5`` or ``"5%"``).
        """
        kind = self._cir.find_part(part)["type"]
        if kind not in self._TOL_MODEL:
            raise ValueError(f"{part} is a {kind}; tolerances are supported on Resistor, Capacitor and Inductor")
        mname, pname = self._TOL_MODEL[kind]
        pct = lambda v: v if isinstance(v, str) else f"{v:g}%"  # noqa: E731
        spec = " ".join(x for x in (f"{pname}=1", f"LOT={pct(lot)}" if lot is not None else "",
                                    f"DEV={pct(dev)}" if dev is not None else "") if x) + " "      # MC9 wants "5% )"
        name = f"{part.upper()}_TOL"
        self._cir.add_text([f".MODEL {name} {mname} ({spec})"])
        self._cir.add_attr(part, "MODEL", name)
        self._dirty = True

    def monte_carlo(self, runs: int = 10, distribution: str = "normal", seed: int = 0, zero_tolerance: bool = False,
                    analysis: str | Sequence[str] | None = None, on: bool = True) -> None:
        """Monte Carlo on/off for the analyses (default all): each analysis then runs ``runs`` times (see ``result.runs``).

        ``distribution``: "normal" or "worst case" (MC9 also lets a part pick GAUSS/UNIFORM/WCASE in its model).
        """
        dist = {"normal": "Normal", "gauss": "Normal", "worst case": "Worst Case", "worst": "Worst Case", "wcase": "Worst Case"}
        if distribution.lower() not in dist:
            raise ValueError(f"distribution must be one of {sorted(set(dist))}")
        names = {"transient": "Transient", "ac": "AC", "dc": "DC", "distortion": "Distortion"}
        for a in ([analysis] if isinstance(analysis, str) else analysis or _ANALYSES):
            sec = self._cir.monte_carlo(names[a.lower()])
            sec.set("Status", "On" if on else "Off")
            sec.set("Distribution", dist[distribution.lower()])
            sec.set("Number of Runs", str(int(runs)))
            sec.set("Seed", str(int(seed)))
            sec.set("Zero Tolerance", "True" if zero_tolerance else "False")
        self._dirty = True

    # ---- inspect / edit parts ----------------------------------------------------------------
    def parts(self) -> dict[str, dict]:
        """{'R1': {'type': 'Resistor', 'RESISTANCE': '200'}, ...}"""
        return {c["attrs"]["PART"]: {"type": c["type"], **{k: v for k, v in c["attrs"].items() if k != "PART"}}
                for c in self._cir.components() if "PART" in c["attrs"]}

    def get(self, part: str, attr: str) -> str:
        c = self._cir.find_part(part)
        key = next((k for k in c["attrs"] if k.lower() == attr.lower()), None)
        if key is None:
            raise KeyError(f"{part} has no {attr!r}; has {list(c['attrs'])}")
        return c["attrs"][key]

    def set(self, part: str, attr: str, value) -> str:
        """c.set('R2','RESISTANCE','233.2k'); c.set('V2','VALUE',21.6). Returns the old value."""
        old = self._cir.set_attr(part, attr, _num(value))
        self._dirty = True
        return old

    # ---- raw analysis settings ----------------------------------------------------------------
    def limits(self, analysis: str, **kv) -> dict:
        """Read/set raw [Limits] keys of an analysis ('transient','ac','dc','distortion','dynamic_ac','dynamic_dc')."""
        lim = self._cir.limits(_LIMIT_NAME.get(analysis.lower(), analysis))
        for k, v in kv.items():
            lim.set(k, _num(v))
        if kv:
            self._dirty = True
        return dict(ln.split("=", 1) for ln in lim.lines if "=" in ln)

    def curves(self, analysis: str, *exprs) -> list[dict]:
        """Replace an analysis' curves. Items: 'v(Ua)', ('F','db(v(Ua))') or a dict:

        ``dict(y="v(out)", x="T", plot=2, xrange=(0, 1e-3), yrange=(-1, 1), ylog=False, xgrid=1e-4, color="#FF0000")``
        (``plot`` groups curves into stacked plots; ``xrange="auto"`` autoscales). A frequency-domain curve in a
        transient analysis is an FFT plot: ``("F", "db(mag(fft(v(out))))")``."""
        name = _LIMIT_NAME.get(analysis.lower(), analysis)
        spec = []
        for e in exprs:
            d = {"y": e} if isinstance(e, str) else {"x": e[0], "y": e[1]} if isinstance(e, tuple) else dict(e)
            spec.append(d)
        self._cir.set_waveforms(name, spec)
        self._dirty = True
        return self._cir.waveforms(name)

    def show(self, **flags) -> None:
        """Schematic display: c.show(voltages=True, currents=False, power=False, condition=False, nodes=False)."""
        keys = {"voltages": "Show Voltages", "currents": "Show Current", "power": "Show Power",
                "condition": "Show Condition", "nodes": "Show Nodes", "pins": "Show Pin Connections",
                "attributes": "Show Attribute Text", "grid_text": "Show Grid Text"}
        sec = next(s for s in self._cir.sections if s.name == "Circuit")
        for k, v in flags.items():
            sec.set(keys[k], "True" if v else "False")
        self._dirty = True

    _MAXIMIZED = "0,3, -1,-1, -4,-30, 0,0,1630,589"   # WINDOWPLACEMENT with showCmd=3 (maximized)

    def _known_names(self) -> set[str]:
        names = {p.lower() for p in self.parts()}
        for sec in self._cir.sections:
            if sec.name == "Grid Text":
                t = (sec.get("Text") or "").strip('"')
                if t and "\u044e" not in t:                  # skip banner texts
                    names.add(t.lower())
        return names

    def _check_expressions(self, analysis: str) -> None:
        """Warn about v(label)/i(part) references MC9 would reject ('label not found')."""
        import re
        known = self._known_names()
        for w in self._cir.waveforms(_LIMIT_NAME[analysis]):
            for expr in (w.get("y"), w.get("x")):
                for ref in re.findall(r"\b[vVi]\(\s*([A-Za-z_][\w.]*)\s*[,)]", expr or ""):
                    if ref.lower() not in known and not ref.isdigit():
                        warnings.warn(f"{analysis}: curve '{expr}' uses '{ref}', which is neither a part nor a named node "
                                      f"(name it with Schematic.node or use a node number); MC9 will report 'label not found'.",
                                      stacklevel=4)

    def _flush(self) -> None:
        for a, steps in self._steps.items():
            self._cir.set_stepping(a, steps, self._nested)
        for sec in self._cir.sections:
            if sec.name in ("Transient", "AC", "DC", "Distortion") and sec.get("Window Placement") is not None:
                sec.set("Window Placement", self._MAXIMIZED if config.maximize_plots else sec.get("Window Placement"))
        for a in _ANALYSES:
            name = _LIMIT_NAME[a]
            if self._cir.waveform_indices(name):
                self._cir.enable_output(name)  # numeric output is what makes results readable
        self._cir.save(str(self.path))
        self._dirty = False

    # ---- live MC9 -----------------------------------------------------------------------------
    def _session(self) -> ui.MC9:
        if self._dirty:
            self._flush()
        h = hashlib.sha1(self.path.read_bytes()).hexdigest()
        if self._ui is None or h != self._hash:
            if self._ui is not None:
                self._ui.close()
            self._ui, self._hash = ui.MC9(self.name), h
        return self._ui

    def _to_schematic(self, m: ui.MC9) -> None:
        if m.mode != "schematic":
            m.exit_analysis()

    def run(self, analysis: str, timeout: int | None = None) -> Result:
        """Run an analysis with the settings currently in the file; its plot stays open for cursors()/shot()."""
        analysis = analysis.lower()
        if analysis not in _ANALYSES:
            raise ValueError(f"analysis must be one of {_ANALYSES}")
        if analysis != "distortion":
            self._check_expressions(analysis)
        lim = self.limits(analysis)
        npts = int(float(lim.get("NPts", "0") or 0))
        if analysis == "ac" and lim.get("Sweep type", "Auto") != "Log":
            warnings.warn("AC 'Sweep type' is not Log: MC9 writes a coarse, linearly spaced table and cursors "
                          "interpolate between those points (band edges can be off by >10%). "
                          "Use c.ac(fmin, fmax, points=401).", stacklevel=3)
        elif analysis in ("transient", "ac") and npts and npts < 200:
            warnings.warn(f"{analysis}: NPts={npts} gives only {npts} numeric rows; raise points "
                          "(the table, not the simulation step, limits measurement accuracy).", stacklevel=3)
        m = self._session()
        self._to_schematic(m)
        path = m.run(analysis, timeout)
        self.last = Result(analysis, path)
        return self.last

    # ---- friendly analyses --------------------------------------------------------------------
    def ac(self, fmin: float = 1, fmax: float = 2e7, points: int = 401, curves: Sequence | None = None,
           temp=None, run: bool = True, **limits) -> Result | None:
        """AC sweep (always logarithmic). curves default: keep the file's, e.g. ['db(v(Ua)/v(Ue))','ph(v(Ua)/v(Ue))']."""
        kv = {"FRange": f"{_num(fmax)},{_num(fmin)}", "NPts": int(points), "Sweep type": "Log"}
        if temp is not None:
            kv.update(self._temps(temp))
        self.limits("ac", **kv, **limits)
        if curves:
            self.curves("ac", *[("F", c) if isinstance(c, str) else c for c in curves])
        return self.run("ac") if run else None

    def transient(self, t_stop, t_start=0, points: int = 1001, curves: Sequence | None = None, max_step=None,
                  temp=None, state: str = "Zero", run: bool = True, **limits) -> Result | None:
        """Transient. Numeric table = `points` rows between t_start and t_stop; steady-state: t_start > 0."""
        ts = float(t_stop) if not isinstance(t_stop, str) else resmod.parse_value(t_stop)
        t0 = float(t_start) if not isinstance(t_start, str) else resmod.parse_value(t_start)
        step = max_step if max_step is not None else (ts - t0) / points
        kv = {"TRange": f"{_num(t_stop)},{_num(t_start)}", "TStep": _num(step), "NPts": int(points), "StateVar": state}
        if temp is not None:
            kv.update(self._temps(temp))
        self.limits("transient", **kv, **limits)
        if curves:
            self.curves("transient", *[("T", c) if isinstance(c, str) else c for c in curves])
        return self.run("transient") if run else None

    def dc(self, source: str, start, stop, step, curves: Sequence | None = None, temp=None, run: bool = True,
           **limits) -> Result | None:
        """DC sweep of a source/part: c.dc('V2', 0, 20, 0.5, ['v(5)']). temp may be a list -> one run per temperature."""
        a, b, s = (resmod.parse_value(v) if isinstance(v, str) else float(v) for v in (start, stop, step))
        kv = {"I1": source, "I1Range": f"{_num(stop)},{_num(start)},{_num(step)}", "Sweep1 type": "Linear",
              "NPts": max(int(round((b - a) / s)) + 1, 2)}
        if temp is not None:
            kv.update(self._temps(temp))
        self.limits("dc", **kv, **limits)
        if curves:
            self.curves("dc", *[("DCINPUT1", c) if isinstance(c, str) else c for c in curves])
        return self.run("dc") if run else None

    def distortion(self, f0, source: str, amplitude, out: str, cycles: int = 20, max_step=None, temp=25,
                   run: bool = True, **limits) -> Result | None:
        """Harmonic distortion analysis (HARM/IHD/THD curves of `out` at fundamental f0)."""
        f = resmod.parse_value(f0) if isinstance(f0, str) else float(f0)
        amps = amplitude if isinstance(amplitude, str) else ",".join(_num(a) for a in (
            amplitude if isinstance(amplitude, Iterable) and not isinstance(amplitude, (int, float)) else [amplitude]))
        kv = {"F0": _num(f0), "ISource": source, "ISourceAmp": amps, "OutExpr": out, "Cycles": int(cycles),
              "Temp": _num(temp), "AmpMethod": "List"}
        if max_step is not None:
            kv["TStep"] = _num(max_step)
        self.limits("distortion", **kv, **limits)
        fn = f"{f:g}"
        self.curves("distortion",
                    dict(x="F", y=f"HARM({out})", plot=1), dict(x="F", y=f"IHD(HARM({out}),{fn})", plot=2),
                    dict(x="F", y=f"THD(HARM({out}),{fn})"), dict(x="T", y=out, plot=4))
        return self.run("distortion") if run else None

    def op(self) -> OP:
        """DC operating point: node voltages and device tables (IC, gm, power, ...). Fast: no waveform run."""
        sec = next(x for x in self._cir.sections if x.name == "Transient")
        old = sec.get("OperPointOnly")
        sec.set("OperPointOnly", "True")
        self._dirty = True
        try:
            m = self._session()
            self._to_schematic(m)
            path = m.run("transient")
        finally:
            sec.set("OperPointOnly", old or "False")
            self._dirty = True   # next run restarts MC9 with the normal setting
        return OP(path)

    @staticmethod
    def _temps(temp) -> dict:
        if isinstance(temp, (list, tuple)):
            return {"Temp": ",".join(_num(t) for t in temp), "Temperature Type": "List"}
        return {"Temp": _num(temp), "Temperature Type": "Linear"}

    # ---- dynamic (schematic overlay) analyses --------------------------------------------------
    def dynamic_dc(self, temperature: float = 25, slider_percent: float = 1, text: bool = False) -> None:
        """Node voltages/currents drawn on the schematic (like lab-report 'режим спокою' figures)."""
        self.limits("dynamic_dc", Temp=temperature, SliderPer=slider_percent, PlaceText="True" if text else "False")
        m = self._session()
        self._to_schematic(m)
        m.dynamic_dc()

    def dynamic_ac(self, freq, temperature: float = 25, first: str = "Mag", second: str = "PhaseDeg",
                   slider_percent: float = 10, text: bool = False) -> None:
        """Phasors on the schematic. first: Mag|MagDB|Real|None, second: PhaseDeg|PhaseRad|Imag|None."""
        self.limits("dynamic_ac", Temp=temperature, FreqList=_num(freq), SliderPer=slider_percent,
                    FirstValueDisplay=first, SecondValueDisplay=second, PlaceText="True" if text else "False")
        m = self._session()
        self._to_schematic(m)
        m.dynamic_ac()

    # ---- plot tools / output -------------------------------------------------------------------
    def cursors(self, left, right=None) -> None:
        """Put MC9's cursors at X values in the open plot (MC9 then shows its own cursor table)."""
        self._session().cursors(_num(left), None if right is None else _num(right))

    def back(self) -> None:
        """Leave the analysis window (return to the schematic)."""
        if self._ui is not None and self._ui.mode != "schematic":
            self._ui.exit_analysis()

    def shot(self, file_name: str, region: str = "plot", trim: bool = True) -> Path:
        """Native MC9 screenshot -> sandbox/exchange/<file_name>. region: plot | schematic | window."""
        if "/" in file_name or not file_name.endswith(".png"):
            raise ValueError("file_name must be a plain *.png name")
        crop = None
        side = workspace.exchange() / f"{self.name}.layout.json"
        if region == "schematic" and trim and side.exists():        # tight crop from the builder's own geometry
            import json
            c = json.loads(side.read_text()).get("crop")
            crop = tuple(c) if c else None
        return Path(self._session().screenshot(file_name, region, trim, crop=crop))

    def export(self, dst: str) -> Path:
        """Copy the (edited) circuit to a NEW host path; refuses to overwrite."""
        if self._dirty:
            self._flush()
        d = Path(dst).expanduser()
        if d.exists():
            raise FileExistsError(f"{d} exists; refusing to overwrite")
        shutil.copyfile(self.path, d)
        return d

    def close(self) -> None:
        if self._ui is not None:
            self._ui.close()
            self._ui = None

    def __enter__(self) -> "Circuit":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


_OPEN: dict[str, Circuit] = {}


def safe_name(s: str) -> str:
    return "".join(ch if ch.isascii() and (ch.isalnum() or ch in "_.-") else "_" for ch in s)[:64]


def open(src: str, name: str | None = None) -> Circuit:  # noqa: A001
    """Import a host .cir into the sandbox (read-only on the original) and return a Circuit."""
    p = Path(src).expanduser()
    if p.suffix.lower() != ".cir" or not p.is_file():
        raise ValueError("src must be an existing .cir file")
    name = safe_name(name or p.stem)
    if name in _OPEN:
        _OPEN.pop(name).close()
    shutil.copyfile(p, workspace.path(name))
    _OPEN[name] = Circuit(name)
    return _OPEN[name]


def attach(name: str) -> Circuit:
    """Circuit already in the sandbox (e.g. built with Schematic or imported earlier)."""
    if name not in _OPEN:
        _OPEN[name] = Circuit(name)
    return _OPEN[name]


def close_all() -> None:
    for c in list(_OPEN.values()):
        c.close()
    _OPEN.clear()


atexit.register(close_all)
