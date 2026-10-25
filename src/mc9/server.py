"""MCP server for Micro-Cap 9. A thin layer over the `mc9` Python library (same code path as scripts).

Everything runs in a bwrap+Wine sandbox: originals are copied in (read-only access) and never modified;
`export_circuit` never overwrites. Results are MC9's own numbers and native MC9 screenshots.
"""
from __future__ import annotations

import threading

from mcp.server.mcpserver import Image, MCPServer

from . import api, measure, workspace
from .netlist import Netlist
from .schematic import Schematic

mcp = MCPServer("microcap9")
_LOCK = threading.RLock()          # one virtual display / MC9 at a time


def _c(name: str) -> api.Circuit:
    return api.attach(name)


def _summary(r: api.Result, max_rows: int) -> dict:
    out = []
    for run in r.runs:
        step = max(1, len(run) // max_rows)
        out.append({"label": run.label, "params": run.params, "columns": run.columns, "n_rows": len(run),
                    "rows": [[run._cols[c][i] for c in run.columns] for i in range(0, len(run), step)]})
    return {"analysis": r.analysis, "runs": out}


# ---- files -------------------------------------------------------------------------------------
@mcp.tool()
def list_circuits() -> list[str]:
    """Circuits currently in the sandbox exchange folder (names without .cir)."""
    return sorted(p.stem for p in workspace.exchange().glob("*.cir"))


@mcp.tool()
def import_circuit(src_path: str, name: str | None = None) -> str:
    """Copy a host .cir (read-only access) into the sandbox; returns the sandbox name to use in other tools."""
    with _LOCK:
        return api.open(src_path, name).name


@mcp.tool()
def export_circuit(name: str, dst_path: str) -> str:
    """Copy a sandbox circuit to a NEW host path. Refuses to overwrite anything."""
    with _LOCK:
        return str(_c(name).export(dst_path))


@mcp.tool()
def circuit_info(name: str) -> dict:
    """Parts (type + attributes) and analysis limits/curves of a circuit."""
    c = _c(name)
    return {"parts": c.parts(), "analyses": c._cir.summary()["analyses"]}


@mcp.tool()
def set_component(name: str, part: str, attribute: str, value: str) -> str:
    """Set an attribute, e.g. part='R1', attribute='RESISTANCE', value='4.7k'. Returns the old value."""
    return f"{part}.{attribute}: {_c(name).set(part, attribute, value)} -> {value}"


@mcp.tool()
def set_analysis(name: str, analysis: str, limits: dict[str, str] | None = None, curves: list[dict] | None = None) -> dict:
    """Raw settings: analysis = transient|ac|dc|distortion|dynamic_ac|dynamic_dc; limits = [Limits] keys
    (e.g. {"TRange":"40m,35m"}); curves = [{"y":"v(Ua)","x":"T","plot":1}]. Prefer the *_sweep tools."""
    c = _c(name)
    lim = c.limits(analysis, **(limits or {}))
    if curves:
        c.curves(analysis, *curves)
    return {"limits": lim, "curves": c._cir.waveforms({"ac": "AC", "dc": "DC"}.get(analysis.lower(), analysis.capitalize()))}


# ---- analyses ----------------------------------------------------------------------------------
@mcp.tool()
def ac_sweep(name: str, fmin: float = 1, fmax: float = 2e7, points: int = 401, curves: list[str] | None = None,
             max_rows: int = 40) -> dict:
    """AC analysis (log sweep). curves e.g. ["db(v(Ua)/v(Ue))","ph(v(Ua)/v(Ue))"]. Leaves the plot open."""
    with _LOCK:
        return _summary(_c(name).ac(fmin, fmax, points, curves), max_rows)


@mcp.tool()
def transient(name: str, t_stop: float, t_start: float = 0, points: int = 1001, curves: list[str] | None = None,
              max_step: float | None = None, max_rows: int = 40) -> dict:
    """Transient analysis; table has `points` rows between t_start and t_stop (steady state: t_start > 0)."""
    with _LOCK:
        return _summary(_c(name).transient(t_stop, t_start, points, curves, max_step=max_step), max_rows)


@mcp.tool()
def dc_sweep(name: str, source: str, start: float, stop: float, step: float, curves: list[str] | None = None,
             temps: list[float] | None = None, max_rows: int = 40) -> dict:
    """DC sweep of a source/part; temps -> one run per temperature."""
    with _LOCK:
        return _summary(_c(name).dc(source, start, stop, step, curves, temp=temps), max_rows)


@mcp.tool()
def distortion_plot(name: str, f0: float, source: str, amplitude: float, out: str, cycles: int = 20) -> str:
    """MC9 Distortion analysis window (HARM/IHD/THD plots) for screenshots. Use measure_thd for numbers."""
    with _LOCK:
        _c(name).distortion(f0, source, amplitude, out, cycles=cycles)
    return "distortion plot open; call screenshot"


@mcp.tool()
def operating_point(name: str) -> dict:
    """DC operating point: node voltages and per-device values (IC, IB, VBE, VCE, GM, RPI, power, ...)."""
    with _LOCK:
        op = _c(name).op()
    return {"nodes": op.nodes, "devices": op.devices}


@mcp.tool()
def dynamic_dc(name: str, temperature: float = 25) -> str:
    """Show Dynamic DC node voltages on the schematic. Then call screenshot(region='schematic')."""
    with _LOCK:
        _c(name).dynamic_dc(temperature)
    return "dynamic DC shown"


@mcp.tool()
def dynamic_ac(name: str, freq: float, temperature: float = 25) -> str:
    """Show Dynamic AC phasors (magnitude, phase) on the schematic at one frequency."""
    with _LOCK:
        _c(name).dynamic_ac(freq, temperature)
    return "dynamic AC shown"


@mcp.tool()
def place_cursors(name: str, left: str, right: str | None = None) -> str:
    """Put MC9's cursors at X values in the open plot (SI suffixes ok: '169.1', '23.01k')."""
    with _LOCK:
        _c(name).cursors(left, right)
    return "cursors placed"


@mcp.tool()
def exit_analysis(name: str) -> str:
    """Close the analysis window and return to the schematic."""
    with _LOCK:
        _c(name).back()
    return "back to schematic"


@mcp.tool()
def screenshot(name: str, file_name: str, region: str = "plot") -> list:
    """Native MC9 screenshot (never re-rendered). region: plot | schematic | window. Saved to sandbox/exchange."""
    with _LOCK:
        path = _c(name).shot(file_name, region)
    return [str(path), Image(path=str(path))]


# ---- measurements ------------------------------------------------------------------------------
@mcp.tool()
def measure_bandwidth(name: str, expr: str, fmin: float = 1, fmax: float = 2e7, cursors: bool = True) -> dict:
    """-3 dB band of a gain curve in dB, e.g. expr='db(v(Ua)/v(Ue))'. Optionally puts MC9 cursors on the edges."""
    with _LOCK:
        bw = measure.bandwidth(_c(name), expr, fmin, fmax, cursors=cursors)
    return {"g0_db": bw.g0_db, "f0": bw.f0, "f_low": bw.f_low, "f_high": bw.f_high}


@mcp.tool()
def measure_rin(name: str, node_v: str, current: str, f: float) -> float:
    """Input resistance |v(node)/i(part)| at f, e.g. node_v='v(Ue)', current='i(R1)'."""
    with _LOCK:
        return measure.rin(_c(name), node_v, current, f)


@mcp.tool()
def measure_rout(name: str, out: str, load: str, f: float) -> float:
    """Output resistance by load removal (load part gets 1T temporarily)."""
    with _LOCK:
        return measure.rout(_c(name), out, load, f)


@mcp.tool()
def measure_thd(name: str, f0: float, source: str, amplitude: float, out: str) -> dict:
    """Harmonic distortion from a steady-state transient DFT: harmonic amplitudes, K_n [%], THD [%]."""
    with _LOCK:
        d = measure.thd(_c(name), f0, source, amplitude, out)
    return {"h": d["h"], "k_pct": d["k_pct"], "thd_pct": d["thd_pct"]}


# ---- schematics --------------------------------------------------------------------------------
@mcp.tool()
def build_schematic(name: str, parts: list[dict], wires: list[list], nodes: list[dict] | None = None,
                    labels: str = "dc") -> dict:
    """Create a circuit. parts: [{"id":"R1","kind":"R","value":"1k","at":[x,y],"rot":0,"extra":{"MODEL":"BF420"}}];
    kinds: R C L V VB I D Q QP GND OPAMP VSIN VPULSE M. wires: [["R1.Plus","R2.Minus"], ["V1.Minus",[0,17]]] where an
    endpoint is "PART.Pin" or [x,y] grid. nodes: [{"name":"Ue","at":"R1.Plus"}]. Returns audit warnings."""
    with _LOCK:
        s = Schematic()
        byid = {}
        for p in parts:
            byid[p["id"]] = s.add(p["kind"], p.get("id") if p["kind"].upper() != "GND" else None, p.get("value"),
                                  tuple(p.get("at", (0, 0))), p.get("rot"), **p.get("extra", {}))

        def pt(x):
            if isinstance(x, str):
                pid, pin = x.split(".", 1)
                return byid[pid].pin(pin)
            return tuple(x)
        for a, b in wires:
            s.wire(pt(a), pt(b))
        for n in nodes or []:
            s.node(n["name"], pt(n["at"]))
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            s.build(name, labels=labels)
        return {"circuit": name, "warnings": [str(x.message) for x in w], "zoom": s.zoom}


@mcp.tool()
def build_netlist(name: str, parts: list[dict], labels: str = "dc", mode: str = "dc") -> dict:
    """Describe a circuit SPICE-style and let mc9 place and route it automatically.
    parts: [{"kind":"R","name":"R1","nodes":["in","out"],"value":"1k"}, {"kind":"Q","name":"Q1","nodes":["col","b","0"],"value":"BF420"}].
    Node order: R/C/L = [first, second]; V/VB/I = [plus, minus]; D = [anode, cathode]; Q/QP = [collector, base, emitter];
    M = [drain, gate, source, body]; OPAMP = [plus, minus, out, vcc, vee]. Node "0" is ground. The first source with
    Sin/Pulse/AC is the input. labels/mode = "dc" | "ac" (room for voltage boxes). Returns warnings and notes."""
    with _LOCK:
        nl = Netlist()
        for p in parts:
            nl.add(p["kind"], p["name"], list(p["nodes"]), p.get("value"), **p.get("extra", {}))
        sch = nl.schematic(mode=mode)
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            sch.build(name, labels=labels)
        return {"circuit": name, "warnings": [str(x.message) for x in w], "notes": sch.notes, "zoom": sch.zoom}


# ---- stepping, tolerances, Monte Carlo, optimizer -------------------------------------------------
@mcp.tool()
def step_parameter(name: str, what: str, start: str, stop: str | None = None, step: str | None = None,
                   param: str | None = None, method: str | None = None, kind: str = "component",
                   analysis: str | None = None) -> str:
    """Add a stepped variable: later analyses run once per value ("runs" with their "params").
    Linear: what="R1", start="1k", stop="3k", step="1k". Log: method="log" (step = multiplier). List: start="1n,10n,100n".
    Model parameter: kind="model", what="BF420", param="BF". analysis: transient|ac|dc|distortion (default all)."""
    with _LOCK:
        _c(name).step(what, start, stop, step, param=param, method=method, kind=kind, analysis=analysis)
        return "ok"


@mcp.tool()
def clear_steps(name: str) -> str:
    """Switch stepping off."""
    with _LOCK:
        _c(name).clear_steps()
        return "ok"


@mcp.tool()
def set_tolerance(name: str, part: str, lot: str | None = None, dev: str | None = None) -> str:
    """Tolerance of a resistor/capacitor/inductor for Monte Carlo, e.g. lot="5%" (lot-wide) and/or dev="1%" (per device)."""
    with _LOCK:
        _c(name).tolerance(part, lot=lot, dev=dev)
        return "ok"


@mcp.tool()
def monte_carlo(name: str, runs: int = 10, distribution: str = "normal", seed: int = 0, analysis: str | None = None,
                on: bool = True) -> str:
    """Monte Carlo on/off. Each analysis then returns `runs` runs (Case=1 is the nominal one). distribution: normal | worst case."""
    with _LOCK:
        _c(name).monte_carlo(runs, distribution, seed, analysis=analysis, on=on)
        return "ok"


@mcp.tool()
def add_model_text(name: str, lines: list[str]) -> str:
    """Add netlist text (.MODEL / .DEFINE / .PARAMETERS ...) to the circuit's text page."""
    with _LOCK:
        _c(name).model(*lines)
        return "ok"


@mcp.tool()
def optimize(name: str, params: dict[str, list[float]], goals: list[list], analysis: str = "ac") -> dict:
    """MC9's optimizer (native engine): params {"R1": [low, high]}, goals [["equals", "Y_Level(db(v(out)),1,1,2000)", -3.0103]]
    (kinds: equals | minimize | maximize). At most 4 of each. The found values are applied to the circuit."""
    with _LOCK:
        return _c(name).optimize({k: tuple(v) for k, v in params.items()}, [tuple(g) for g in goals], analysis=analysis)


@mcp.tool()
def stop_mc9() -> str:
    """Close MC9 sessions and free memory."""
    with _LOCK:
        api.close_all()
    return "stopped"


@mcp.tool()
def reset_sandbox() -> str:
    """Discard the working Wine prefix; it is re-created from the pristine snapshot."""
    with _LOCK:
        api.close_all()
        from .backends import linux_wine
        linux_wine.reset()
    return "ok"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
