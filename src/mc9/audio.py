"""Audio power amplifier (class AB, bipolar, inverting, dual supply): design numbers, a starter circuit and the lab measurements.

The typical coursework: from a table row (P_out, R_load, R_in, f_low, f_high, THD) design, simulate and report. This module gives

* ``Specs`` - the requirements, with the derived numbers (peak voltage/current, gain, supply voltage, feedback resistors);
* ``power_amplifier(specs)`` - a starter ``Netlist`` (op-amp + complementary Darlington output stage inside the feedback loop);
* ``Bench`` - every measurement of the usual report, each one running MC9 and keeping MC9's own plots:
  AC/phase response, transients at f_low / f_0 / f_high, clipping at double amplitude, square wave and slew rate, THD at 1 and 10 kHz,
  maximum power at 10 % THD, power bandwidth, output resistance, quiescent point, supply current, efficiency, transistor dissipation,
  and everything again at 0 and 70 degC.

    from mc9 import audio
    s = audio.Specs(p_out=24, r_load=6, r_in=60e3, f_low=25, f_high=18e3, thd=0.3)
    c = audio.power_amplifier(s).build("ppzch", labels="dc")
    bench = audio.Bench(c, s)
    print(bench.report())
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import measure, sources
from .netlist import Netlist
from .schematic import Schematic


def _si(x: float) -> str:
    for exp, suf in ((9, "G"), (6, "MEG"), (3, "k"), (0, ""), (-3, "m"), (-6, "u"), (-9, "n"), (-12, "p")):
        if abs(x) >= 10 ** exp * 0.9999 or exp == -12:
            return f"{x / 10 ** exp:.4g}{suf}"
    return f"{x:g}"


@dataclass
class Specs:
    p_out: float                 # W, nominal output power
    r_load: float                # ohm
    r_in: float                  # ohm (the input resistance of an inverting stage is the input resistor)
    f_low: float                 # Hz, -3 dB
    f_high: float                # Hz, -3 dB
    thd: float = 0.5             # %, maximum nonlinear distortion
    u_in: float = 1.0            # V, nominal input amplitude
    f0: float = 1000.0           # Hz, "middle" frequency
    temps: tuple = (0, 25, 70)   # degC, the operating range and the nominal point

    @property
    def v_out(self) -> float:    # V, output amplitude at nominal power
        return math.sqrt(2 * self.p_out * self.r_load)

    @property
    def i_out(self) -> float:    # A, output current amplitude
        return self.v_out / self.r_load

    @property
    def gain(self) -> float:
        return self.v_out / self.u_in

    @property
    def vcc(self) -> float:      # V, each supply: output amplitude + saturation, emitter resistor and driver drops
        return math.ceil(self.v_out + 3.5 + 0.35 * self.i_out) + 1

    @property
    def xi(self) -> float:       # supply voltage utilisation, nominal
        return self.v_out / self.vcc

    @property
    def p_supply(self) -> float:  # W, ideal class B supply power at nominal output
        return 2 * self.vcc * self.v_out / (math.pi * self.r_load)

    @property
    def efficiency(self) -> float:
        return self.p_out / self.p_supply

    @property
    def p_dissipation_max(self) -> float:   # W, class B: total worst case at Vout = 2 Vcc / pi, both output transistors
        return 2 * self.vcc ** 2 / (math.pi ** 2 * self.r_load)

    def summary(self) -> dict:
        return {"Uout_m, V": self.v_out, "Iout_m, A": self.i_out, "gain": self.gain, "Vcc, V": self.vcc,
                "xi": self.xi, "P_supply, W": self.p_supply, "efficiency": self.efficiency,
                "P_diss max (both), W": self.p_dissipation_max}


def _r_bias(s: Specs, i_bias: float) -> str:
    """Resistor from each rail to the bias diode string: (2 Vcc - 4 Vd) / (2 I)."""
    return _si((2 * s.vcc - 2.6) / (2 * i_bias))


def power_amplifier(s: Specs, op_amp: str = "LF411", driver=("BD139", "BD140"), power=("MJ15003", "MJ15004"),
                    r_trim: float = 1.0, i_bias: float = 0.003) -> Netlist:
    """Inverting amplifier: R_in -> op-amp (gain R_f/R_in) -> complementary emitter-follower pair (driver + power transistor
    per side, bias from a diode string) with the feedback taken from the load. Nodes: in, out, inv, a, vp, vm."""
    rf = s.gain * s.r_in
    cf = 1 / (2 * math.pi * rf * 4 * s.f_high)          # feedback pole at 4 x f_high
    n = Netlist()
    n.V("V1", "in", "0", sources.sine(s.u_in, s.f0))
    n.C("CIN", "in", "x", _si(1 / (2 * math.pi * s.r_in * s.f_low)))     # the lower -3 dB edge: R_in C_in at f_low
    n.R("RIN", "x", "inv", _si(s.r_in))
    n.R("RF", "inv", "out", _si(rf))
    n.C("CF", "inv", "out", _si(cf))
    n.R("RG", "0", "pg", _si(1 / (1 / s.r_in + 1 / rf)))             # bias-current balance for the + input
    n.OPAMP("U1", "pg", "inv", "a", "vp", "vm", op_amp)
    n.R("RUP", "vp", "nb", _r_bias(s, i_bias))
    n.D("D1", "nb", "d1", "1N4148")
    n.D("D2", "d1", "a1", "1N4148")
    n.R("RT1", "a1", "a", _si(r_trim))
    n.R("RT2", "a", "a2", _si(r_trim))
    n.D("D3", "a2", "d3", "1N4148")
    n.D("D4", "d3", "pb", "1N4148")
    n.R("RDN", "pb", "vm", _r_bias(s, i_bias))
    n.Q("Q1", "vp", "nb", "e1", driver[0])
    n.Q("Q3", "vp", "e1", "eo", power[0])
    n.R("RE1", "e1", "out", "100")
    n.R("RE3", "eo", "out", "0.33")
    n.QP("Q2", "vm", "pb", "e2", driver[1])
    n.QP("Q4", "vm", "e2", "ep", power[1])
    n.R("RE2", "out", "e2", "100")
    n.R("RE4", "out", "ep", "0.33")
    n.R("RZ", "out", "z", "10")
    n.C("CZ", "z", "0", "100n")
    n.R("RL", "out", "0", _si(s.r_load))
    n.VB("VSP", "vp", "0", _si(s.vcc))
    n.VB("VSM", "0", "vm", _si(s.vcc))
    return n


def schematic(s: Specs, op_amp: str = "LF411", driver=("BD139", "BD140"), power=("MJ15003", "MJ15004"),
              r_trim: float = 1.0, i_bias: float = 0.003) -> Schematic:
    """The same amplifier as `power_amplifier`, drawn by hand (the automatic placer is made for small stages): signal left to
    right, bias string and output pairs in the middle, load and Zobel network on the right; the supplies are joined by name."""
    rf = s.gain * s.r_in
    cf = 1 / (2 * math.pi * rf * 4 * s.f_high)
    rbias = _r_bias(s, i_bias)
    d = Schematic()
    add, W = d.add, d.wire
    v1 = add("V", "V1", sources.sine(s.u_in, s.f0), at=(0, 16), rot=3)
    cin = add("C", "CIN", _si(1 / (2 * math.pi * s.r_in * s.f_low)), at=(4, 10))
    rin = add("R", "RIN", _si(s.r_in), at=(12, 10))
    u1 = add("OPAMP", "U1", at=(22, 4), MODEL=op_amp)
    add("GND", None, at=(0, 19))
    rg = add("R", "RG", _si(1 / (1 / s.r_in + 1 / rf)), at=(19, -2), rot=1)
    gp = add("GND", None, at=(19, -6), rot=3)
    W(v1.Plus, cin.Minus)
    d.node("in", (2, 10))
    W(cin.Plus, rin.Minus)
    W(rin.Plus, u1["Minus input"])
    W(v1.Minus, (0, 19))
    W(u1["Plus input"], rg.Plus)
    W(rg.Minus, gp.PinA)
    d.node("inv", (20, 10))
    W(u1["VCC"], (26, 0))
    W(u1["VEE"], (26, 14))
    d.node("vp", (26, 0))
    d.node("vm", (26, 14))
    # bias string and op-amp output node 'a'
    rup = add("R", "RUP", rbias, at=(44, -12), rot=1)
    d1 = add("D", "D1", at=(44, 0), rot=3, MODEL="1N4148")
    d2 = add("D", "D2", at=(44, 6), rot=3, MODEL="1N4148")
    rt1 = add("R", "RT1", _si(r_trim), at=(44, 6), rot=1)
    rt2 = add("R", "RT2", _si(r_trim), at=(44, 12), rot=1)
    d3 = add("D", "D3", at=(44, 24), rot=3, MODEL="1N4148")
    d4 = add("D", "D4", at=(44, 30), rot=3, MODEL="1N4148")
    rdn = add("R", "RDN", rbias, at=(44, 30), rot=1)
    d.node("vp", rup.Minus)
    W(rdn.Plus, (44, 39))
    d.node("vm", (44, 39))
    W(u1.Output, (31, 12), via="v")
    W((31, 12), rt1.Plus)
    d.node("a", (35, 12))
    W(rup.Plus, d1.Anode)
    W(d1.Cathode, d2.Anode)
    W(d2.Cathode, rt1.Minus)
    W(rt2.Minus, rt1.Plus)
    W(rt2.Plus, d3.Anode)
    W(d3.Cathode, d4.Anode)
    W(d4.Cathode, rdn.Minus)
    # output pairs
    q1 = add("Q", "Q1", at=(52, -6), MODEL=driver[0])
    q3 = add("Q", "Q3", at=(64, -3), MODEL=power[0])
    re1 = add("R", "RE1", "100", at=(59, 0), rot=1)
    re3 = add("R", "RE3", "0.33", at=(67, 0), rot=1)
    q2 = add("QP", "Q2", at=(52, 30), MODEL=driver[1])
    q4 = add("QP", "Q4", at=(64, 27), MODEL=power[1])
    re2 = add("R", "RE2", "100", at=(59, 21), rot=1)
    re4 = add("R", "RE4", "0.33", at=(67, 18), rot=1)
    W(d1.Anode, q1.Base)                     # nb: the upper end of the bias string
    W(d4.Cathode, q2.Base)                   # pb: the lower end
    W(q1.Emitter, q3.Base)
    W((59, -3), re1.Minus)
    W(q3.Emitter, re3.Minus)
    W(q2.Emitter, q4.Base)
    W((59, 27), re2.Plus)
    W(q4.Emitter, re4.Plus)
    W(q1.Collector, (55, -12))
    W(q3.Collector, (67, -9))
    W(q2.Collector, (55, 36))
    W(q4.Collector, (67, 33))
    for pt in ((55, -12), (67, -9)):
        d.node("vp", pt)
    for pt in ((55, 36), (67, 33)):
        d.node("vm", pt)
    # output bus, Zobel network, load
    W(re1.Plus, (59, 15))
    W(re3.Plus, (67, 15))
    W(re2.Minus, (59, 15))
    W(re4.Minus, (67, 15))
    W((59, 15), (84, 15))
    rz = add("R", "RZ", "10", at=(74, 15), rot=1)
    cz = add("C", "CZ", "100n", at=(74, 21), rot=1)
    gz = add("GND", None, at=(74, 27))
    rl = add("R", "RL", _si(s.r_load), at=(80, 15), rot=1)
    gl = add("GND", None, at=(80, 21))
    W(rz.Plus, cz.Minus)
    W(cz.Plus, gz.PinA)
    W(rl.Plus, gl.PinA)
    d.node("out", (84, 15))
    # feedback: R_F || C_F from the output back to the inverting input
    rfp = add("R", "RF", _si(rf), at=(26, -18))
    cfp = add("C", "CF", _si(cf), at=(26, -14))
    W(rfp.Plus, (40, -18))
    d.node("out", (40, -18))                 # joined to the output by name
    W(rfp.Minus, (22, -18))                  # joined to the inverting input by name
    d.node("inv", (22, -18))
    W(cfp.Minus, (22, -14))
    W((22, -14), (22, -18))
    W(cfp.Plus, (36, -14))
    W((36, -14), (36, -18))
    # supplies
    vp = add("VB", "VSP", _si(s.vcc), at=(96, -4), rot=3)
    vm = add("VB", "VSM", _si(s.vcc), at=(96, 33), rot=3)
    gvp = add("GND", None, at=(96, -1))
    gvm = add("GND", None, at=(96, 24), rot=3)
    W(vp.Minus, gvp.PinA)
    W(vm.Plus, gvm.PinA)
    d.node("vp", vp.Plus)
    d.node("vm", (96, 40))
    W(vm.Minus, (96, 40))
    return d


# ----------------------------------------------------------------------------------------------
def phase_margin_from_peaking(peaking_db: float) -> float | None:
    """Phase margin (deg) of a second-order loop from the closed-loop peaking (dB): the usual estimate when the loop gain
    itself is not accessible. 0 dB peaking -> None (no peaking: comfortably stable, margin above ~65 deg)."""
    if peaking_db <= 0.05:
        return None
    mp = 10 ** (peaking_db / 20)
    # Mp = 1 / (2 z sqrt(1 - z^2))  ->  z^2 = (1 - sqrt(1 - 1/Mp^2)) / 2
    z = math.sqrt((1 - math.sqrt(max(0.0, 1 - 1 / mp ** 2))) / 2)
    return math.degrees(math.atan2(2 * z, math.sqrt(math.sqrt(1 + 4 * z ** 4) - 2 * z ** 2)))


def edge_time(t: list[float], y: list[float], start: float, end: float) -> float | None:
    """Time the signal needs to go from level `start` to level `end` (rising or falling): the first crossing of `start`
    and the next crossing of `end` after it, interpolated linearly. None when the edge is not in the data."""
    def crossing(level, i0, up):
        for i in range(i0, len(y) - 1):
            a, b = y[i] - level, y[i + 1] - level
            if (a < 0 <= b) if up else (a > 0 >= b):
                return t[i] + (t[i + 1] - t[i]) * (0 - a) / (b - a), i
        return None
    up = end > start
    first = crossing(start, 0, up)
    if first is None:
        return None
    second = crossing(end, first[1], up)
    return None if second is None else second[0] - first[0]


class Bench:
    """The measurements of the audio-amplifier coursework, on a circuit built by `power_amplifier` / `schematic`.

    Every method runs MC9, saves MC9's own plot (``shot=True``) and returns plain numbers. Names of the parts can be changed in
    the constructor when you use your own circuit."""

    def __init__(self, c, specs: Specs, source: str = "V1", out: str = "out", inp: str = "in", load: str = "RL",
                 supplies: tuple = ("VSP", "VSM"), out_devices: tuple = ("Q3", "Q4"), prefix: str = ""):
        self.c, self.s = c, specs
        self.src, self.out, self.inp, self.load, self.supplies, self.devices = source, out, inp, load, supplies, out_devices
        self.prefix = prefix or c.name
        self.log: list[str] = []

    # ---- helpers ------------------------------------------------------------------------------
    def _sine(self, amp, f):
        self.c.set(self.src, "VALUE", sources.sine(amp, f))

    def _shot(self, name: str, shot: bool, region: str = "plot"):
        return str(self.c.shot(f"{self.prefix}_{name}.png", region)) if shot else None

    def _cycles(self, f: float, cycles: int = 6, settle: int = 3, per: int = 60):
        T = 1 / f
        return dict(t_stop=(cycles + settle) * T, t_start=settle * T, points=cycles * per + 1, max_step=T / (per * 4))

    # ---- frequency domain ---------------------------------------------------------------------
    def ac_response(self, fmin: float = 1.0, fmax: float = 1e7, shot: bool = True, temps=None) -> dict:
        """A0 at f0, the -3 dB edges (against the maximum), phase there, peaking and the phase-margin estimate."""
        c, s = self.c, self.s
        db, ph = f"db(v({self.out})/v({self.inp}))", f"ph(v({self.out})/v({self.inp}))"
        c.set(self.src, "VALUE", sources.sine(s.u_in, s.f0))
        r = c.ac(fmin, fmax, 801, [db, ph], temp=temps if temps is not None else 25)
        res = []
        for run in r.runs:
            f_pk, g_pk = run.peak(db)
            lows = [f for f in run.cross(db, g_pk - 3) if f < f_pk]
            highs = [f for f in run.cross(db, g_pk - 3) if f > f_pk]
            f_lo, f_hi = (max(lows) if lows else None), (min(highs) if highs else None)
            a0 = run.value_at(db, s.f0)
            peaking = g_pk - a0
            res.append({"temperature": run.params.get("Temperature", 25.0), "A0_db": a0, "A0": 10 ** (a0 / 20),
                        "f_low": f_lo, "f_high": f_hi, "f_peak": f_pk, "gain_max_db": g_pk,
                        "phase_f0": run.value_at(ph, s.f0), "phase_low": run.value_at(ph, f_lo) if f_lo else None,
                        "phase_high": run.value_at(ph, f_hi) if f_hi else None, "peaking_db": peaking,
                        "phase_margin_est": phase_margin_from_peaking(max(peaking, 0.0))})
        if shot:
            edges = [x for x in (res[-1]["f_low"], res[-1]["f_high"]) if x]
            if edges:
                c.cursors(edges[0], edges[1] if len(edges) > 1 else None)
            self._shot("ac_gain_phase", True)
        return {"runs": res, "nominal": next((x for x in res if abs(x["temperature"] - 25) < 1e-6), res[0]), "result": r}

    def output_resistance(self, f: float | None = None, heavy: float = 0.5) -> float:
        """R_out from two loads, R_L and a heavy `heavy` ohm: R_out = (V1 - V2) / (V2/R2 - V1/R1). A closed-loop amplifier has
        milliohms, which MC9's 6-digit table cannot show with the load removed - hence the heavy load."""
        c, f = self.c, f or self.s.f0
        expr = f"mag(v({self.out}))"
        lo, hi = max(f / 1000, 1e-3), f * 1000
        r1 = c.get(self.load, "RESISTANCE")
        r1v = measure.resmod.parse_value(r1) if isinstance(r1, str) else float(r1)
        c.set(self.src, "VALUE", sources.sine(self.s.u_in, f))
        v1 = c.ac(lo, hi, 801, [expr], temp=25).value_at(expr, f)
        c.set(self.load, "RESISTANCE", heavy)
        try:
            v2 = c.ac(lo, hi, 801, [expr], temp=25).value_at(expr, f)
        finally:
            c.set(self.load, "RESISTANCE", r1)
        return (v1 - v2) / (v2 / heavy - v1 / r1v)

    # ---- time domain --------------------------------------------------------------------------
    def sine_at(self, f: float, amp: float | None = None, shot: bool = True, temps=None, tag: str = "") -> dict:
        """Steady-state sine at `f` (nominal input amplitude by default): output amplitude, power, supply current, efficiency."""
        c, s = self.c, self.s
        amp = s.u_in if amp is None else amp
        self._sine(amp, f)
        v, ip, im = f"v({self.out})", f"i({self.supplies[0]})", f"i({self.supplies[1]})"
        r = c.transient(**self._cycles(f), curves=[f"v({self.inp})", v, ip, im], temp=temps if temps is not None else 25)
        out = []
        for run in r.runs:
            peak = max(abs(x) for x in run[v])
            rms = math.sqrt(sum(x * x for x in run[v]) / len(run[v]))
            i_p, i_m = (sum(abs(x) for x in run[k]) / len(run[k]) for k in (ip, im))
            p_out, p_sup = rms ** 2 / s.r_load, s.vcc * (i_p + i_m)
            out.append({"temperature": run.params.get("Temperature", 25.0), "f": f, "v_peak": peak, "gain": peak / amp,
                        "v_max": max(run[v]), "v_min": min(run[v]), "p_out": p_out, "i_supply_mean": i_p + i_m,
                        "p_supply": p_sup, "efficiency": p_out / p_sup if p_sup else float("nan")})
        if shot:
            self._shot(f"sine_{tag or int(f)}Hz", True)
        return {"runs": out, "nominal": next((x for x in out if abs(x["temperature"] - 25) < 1e-6), out[0]), "result": r}

    def clipping(self, f: float | None = None, factor: float = 2.0, shot: bool = True) -> dict:
        """Double the nominal input: the output levels where it clips and the supply-voltage utilisation."""
        r = self.sine_at(f or self.s.f0, self.s.u_in * factor, shot=shot, tag="clip")
        n = r["nominal"]
        n["xi"] = min(n["v_max"], -n["v_min"]) / self.s.vcc
        return n

    def square_wave(self, f: float, shot: bool = True) -> dict:
        """+-Uin square wave: rise/fall time (10-90 %), slew rate and overshoot of the output."""
        c, s = self.c, self.s
        T = 1 / f
        c.set(self.src, "VALUE", sources.pulse(-s.u_in, s.u_in, T, rise=min(T / 1e4, 1e-8), fall=min(T / 1e4, 1e-8)))
        v = f"v({self.out})"
        r = c.transient(t_stop=4 * T, t_start=2 * T, points=1201, curves=[f"v({self.inp})", v], max_step=T / 4000)
        y = r[v]
        hi, lo = max(y), min(y)
        span = hi - lo
        l10, l90 = lo + 0.1 * span, lo + 0.9 * span
        t_r = edge_time(r.x, y, l10, l90)
        t_f = edge_time(r.x, y, l90, l10)
        sr_up = 0.8 * span / t_r if t_r else None
        sr_dn = 0.8 * span / t_f if t_f else None
        mid = sorted(y)[len(y) // 2]
        out = {"f": f, "v_high": hi, "v_low": lo, "t_rise": t_r, "t_fall": t_f, "slew_up": sr_up, "slew_down": sr_dn,
               "overshoot_pct": 100 * (hi - sorted(y)[int(0.85 * len(y))]) / max(span, 1e-12)}
        if shot:
            self._shot(f"square_{int(f)}Hz", True)
        out["mid"] = mid
        return out

    # ---- distortion and power -----------------------------------------------------------------
    def distortion(self, f: float, amp: float | None = None, shot: bool = True) -> dict:
        """THD at f for the given input amplitude (nominal by default); MC9's own harmonic plot is saved too."""
        amp = self.s.u_in if amp is None else amp
        self._sine(amp, f)                       # the source may still hold a square wave from an earlier measurement
        d = measure.thd(self.c, f, self.src, amp, f"v({self.out})")
        out = {"f": f, "thd_pct": d["thd_pct"], "k_pct": d["k_pct"], "h": d["h"]}
        if shot:
            self.c.distortion(f, self.src, amp, f"v({self.out})")
            self._shot(f"harmonics_{int(f)}Hz", True)
        return out

    def max_power(self, f: float | None = None, thd_limit: float = 10.0, iterations: int = 9) -> dict:
        """Largest output power with THD <= thd_limit (bisection on the input amplitude)."""
        f = f or self.s.f0
        self._sine(self.s.u_in, f)
        lo, hi = self.s.u_in, self.s.u_in * 2.5
        d_lo = measure.thd(self.c, f, self.src, lo, f"v({self.out})")
        best = d_lo
        for _ in range(iterations):
            mid = (lo + hi) / 2
            d = measure.thd(self.c, f, self.src, mid, f"v({self.out})")
            if d["thd_pct"] <= thd_limit:
                lo, best = mid, d
            else:
                hi = mid
        v1 = best["h"][1]
        return {"f": f, "u_in": lo, "v_out_peak": v1, "p_max": v1 ** 2 / (2 * self.s.r_load), "thd_pct": best["thd_pct"]}

    def power_bandwidth(self, slew: float, v_peak: float | None = None) -> float:
        """Full-power frequency from the slew rate: f = SR / (2 pi V_peak)."""
        return slew / (2 * math.pi * (v_peak or self.s.v_out))

    def dissipation(self, fractions=(0.3, 0.5, 0.64, 0.8)) -> dict:
        """Mean power in the two output transistors at output amplitudes of 0.3 ... 0.8 Vcc: the largest value is the worst case."""
        s = self.s
        expr = [f"pd({d})" for d in self.devices]
        rows = {}
        for fr in fractions:
            amp = fr * s.vcc / abs(self._gain_est())
            self._sine(amp, s.f0)
            r = self.c.transient(**self._cycles(s.f0, 4, 2, 40), curves=expr + [f"v({self.out})"], temp=25)
            run = r.runs[0]
            rows[fr] = sum(sum(run[e]) / len(run[e]) for e in expr)
        worst = max(rows, key=rows.get)
        return {"by_fraction": rows, "worst_fraction": worst, "p_max": rows[worst]}

    def _gain_est(self) -> float:
        return self.s.gain

    # ---- operating point ----------------------------------------------------------------------
    def quiescent(self) -> dict:
        """Output offset and the supply current at rest (input shorted by DC 0)."""
        c = self.c
        c.set(self.src, "VALUE", "DC 0 AC 1 0")
        op = c.op()
        out = {"v_out_dc": op.v(self.out.upper() if self.out.upper() in op.nodes else self.out)}
        try:
            out["i_q_mA"] = {d: op[d]["IC"] * 1e3 for d in self.devices}
        except KeyError:
            pass
        try:
            out["i_rest"] = sum(abs(op[sup]["ISource"]) for sup in self.supplies)
        except KeyError:
            pass
        return out

    def tune_quiescent(self, i_q: float = 0.05, parts=("RUP", "RDN"), lo: float = 500.0, hi: float = 1e5) -> float:
        """Set the bias string resistors (both equal) so each output transistor idles at `i_q` amps."""
        c = self.c
        c.set(self.src, "VALUE", "DC 0 AC 1 0")
        a, b = math.log(lo), math.log(hi)
        for _ in range(9):
            mid = math.exp((a + b) / 2)
            for p in parts:
                c.set(p, "RESISTANCE", mid)
            ic = sum(c.op()[d]["IC"] for d in self.devices) / len(self.devices)
            a, b = (math.log(mid), b) if ic > i_q else (a, math.log(mid))    # larger resistors -> less bias current
            if abs(ic - i_q) / i_q < 0.05:
                break
        return mid


def _f(x, fmt="{:.4g}"):
    return "-" if x is None else fmt.format(x)


def report(b: Bench, shots: bool = True, temps=(0, 25, 70), quick: bool = False) -> dict:
    """Run the whole coursework set and return {quantity: value}; MC9's pictures are saved next to the circuit.

    ``quick=True`` skips the slow searches (maximum power, dissipation sweep)."""
    s = b.s
    out: dict = {"specs": s.summary()}
    ac = b.ac_response(shot=shots, temps=list(temps))
    nom = ac["nominal"]
    out["ac"] = ac["runs"]
    out["A0_db"], out["f_low"], out["f_high"] = nom["A0_db"], nom["f_low"], nom["f_high"]
    out["phase_margin_est"] = nom["phase_margin_est"]
    for tag, f in (("fl", s.f_low), ("f0", s.f0), ("fh", s.f_high)):
        out[f"sine_{tag}"] = b.sine_at(f, shot=shots, tag=tag, temps=list(temps))["runs"]
    out["clipping"] = b.clipping(shot=shots)
    out["square"] = {tag: b.square_wave(f, shot=shots) for tag, f in (("fl", s.f_low), ("f0", s.f0), ("fh", s.f_high))}
    sq = out["square"]["f0"]
    slews = [x for x in (sq["slew_up"], sq["slew_down"]) if x]
    out["slew"] = min(slews) if slews else None
    out["f_power"] = b.power_bandwidth(out["slew"]) if out["slew"] else None
    out["thd"] = {f: b.distortion(f, shot=shots) for f in (1e3, 1e4)}
    out["r_out"] = b.output_resistance()
    out["quiescent"] = b.quiescent()
    n = out["sine_f0"]
    nn = next((x for x in n if abs(x["temperature"] - 25) < 1e-6), n[0])
    out["nominal"] = nn
    if not quick:
        out["max_power"] = b.max_power()
        out["dissipation"] = b.dissipation()
    return out


def format_report(r: dict, s: Specs) -> str:
    """The numbers of `report` as the text table of the explanatory note (requirement | result)."""
    nn = r["nominal"]
    rows = [
        ("Nominal output power, W", f"{s.p_out:g}", _f(nn["p_out"])),
        ("Band -3 dB, Hz", f"{s.f_low:g} .. {s.f_high:g}", f"{_f(r['f_low'])} .. {_f(r['f_high'])}"),
        ("Gain A0 at 1 kHz, dB / times", f"{20 * math.log10(s.gain):.2f} / {s.gain:.2f}", f"{r['A0_db']:.2f} / {10 ** (r['A0_db'] / 20):.2f}"),
        ("THD at 1 kHz, %", f"<= {s.thd:g}", _f(r["thd"][1e3]["thd_pct"])),
        ("THD at 10 kHz, %", f"<= {s.thd:g}", _f(r["thd"][1e4]["thd_pct"])),
        ("Supply voltage utilisation", "-", _f(r["clipping"]["xi"])),
        ("Slew rate, V/us", "-", _f(r["slew"] / 1e6 if r["slew"] else None)),
        ("Full-power frequency, kHz", "-", _f(r["f_power"] / 1e3 if r["f_power"] else None)),
        ("Output resistance, mohm", "-", _f(r["r_out"] * 1e3)),
        ("Output DC offset, V", "-", _f(r["quiescent"]["v_out_dc"])),
        ("Supply current at rest, A", "-", _f(r["quiescent"].get("i_rest"))),
        ("Supply current at nominal power, A", "-", _f(nn["i_supply_mean"])),
        ("Efficiency at nominal power", f"{s.efficiency:.2f} (class B)", _f(nn["efficiency"])),
        ("Phase margin (from peaking), deg", "-", _f(r["phase_margin_est"], "{:.0f}") if r["phase_margin_est"] else "> 65"),
    ]
    if "max_power" in r:
        rows.append(("Max power at THD 10 %, W", "-", _f(r["max_power"]["p_max"])))
    if "dissipation" in r:
        rows.append(("Max dissipation in output transistors, W", f"{s.p_dissipation_max:.1f} (class B)", _f(r["dissipation"]["p_max"])))
    w = max(len(a) for a, _, _ in rows)
    return "\n".join(f"{a:<{w}} | {b:>16} | {c:>12}" for a, b, c in [("Quantity", "Required / theory", "Simulated")] + rows)
