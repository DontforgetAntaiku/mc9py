"""Ready-made teaching circuits as `Netlist`s. Parameters are plain values or MC9 strings ("4.7k").

    import mc9
    from mc9 import library
    c = library.ce_amplifier(vcc=15).build("amp")
"""
from __future__ import annotations

from . import sources
from .netlist import Netlist


def _n(v) -> str:
    return v if isinstance(v, str) else repr(float(v)) if not float(v).is_integer() else str(int(v))


def _si(x: float) -> str:
    """1e5 -> '100k', 4700 -> '4.7k', 2.2e-6 -> '2.2u' (MC9 notation)."""
    for exp, suf in ((9, "G"), (6, "MEG"), (3, "k"), (0, ""), (-3, "m"), (-6, "u"), (-9, "n"), (-12, "p")):
        if abs(x) >= 10 ** exp * 0.9999 or exp == -12:
            return f"{x / 10 ** exp:.6g}{suf}"
    return f"{x:g}"


def voltage_divider(vin=10, r1="1k", r2="2k") -> Netlist:
    """DC divider: nodes in, out."""
    n = Netlist()
    n.V("V1", "in", "0", f"DC {_n(vin)}")
    n.R("R1", "in", "out", r1)
    n.R("R2", "out", "0", r2)
    return n


def rc_lowpass(r="1k", c="159.155n", amplitude=1, freq=1e3) -> Netlist:
    """First-order RC low-pass (fc = 1/2piRC = 1 kHz by default): nodes in, out."""
    n = Netlist()
    n.V("V1", "in", "0", sources.sine(amplitude, freq))
    n.R("R1", "in", "out", r)
    n.C("C1", "out", "0", c)
    return n


def rc_highpass(c="159.155n", r="1k", amplitude=1, freq=1e3) -> Netlist:
    """First-order RC high-pass: nodes in, out."""
    n = Netlist()
    n.V("V1", "in", "0", sources.sine(amplitude, freq))
    n.C("C1", "in", "out", c)
    n.R("R1", "out", "0", r)
    return n


def rlc_lowpass(r="50", l="10m", c="1u", rl="1k", amplitude=1, freq=1e3) -> Netlist:
    """Series R-L into a C || load: second-order low-pass. Nodes in, a, out."""
    n = Netlist()
    n.V("V1", "in", "0", sources.sine(amplitude, freq))
    n.R("R1", "in", "a", r)
    n.L("L1", "a", "out", l)
    n.C("C1", "out", "0", c)
    n.R("RL", "out", "0", rl)
    return n


def diode_clipper(amplitude=5, freq=1e3, r="1k", model="1N4148") -> Netlist:
    """Two-sided diode limiter (antiparallel diodes to ground): nodes in, out."""
    n = Netlist()
    n.V("V1", "in", "0", sources.sine(amplitude, freq))
    n.R("R1", "in", "out", r)
    n.D("D1", "out", "0", model)
    n.D("D2", "0", "out", model)
    return n


def ce_amplifier(vcc=18, rb="233.2k", rc="1.2k", rl="1.2k", rs="200", c1="3.47u", c2="12n", c3="553n",
                 model="BF420", amplitude=3.5e-3, freq=2224) -> Netlist:
    """RC-coupled common-emitter stage with a base bias resistor. Nodes: src, ue (stage input), b, col, ua (output), vcc."""
    n = Netlist()
    n.V("V1", "src", "0", sources.sine(amplitude, freq))
    n.R("R1", "src", "ue", rs)
    n.C("C1", "ue", "b", c1)
    n.R("R2", "vcc", "b", rb)
    n.Q("Q1", c="col", b="b", e="0", model=model)
    n.R("R3", "vcc", "col", rc)
    n.C("C2", "col", "0", c2)
    n.C("C3", "col", "ua", c3)
    n.R("R4", "ua", "0", rl)
    n.VB("V2", "vcc", "0", _n(vcc))
    return n


def ce_feedback_amplifier(vcc=18, rb1="62.5k", rb2="3.12k", rc="1.2k", rl="1.2k", rg="100", cb="396n", cc="737n",
                          ch="110p", model="BF420", amplitude=10e-3, freq=1000) -> Netlist:
    """Common-emitter stage with parallel voltage feedback (RB1 collector->base, CH across it). Nodes: src, ue, x, b, col, ua, vcc."""
    n = Netlist()
    n.V("V1", "src", "0", sources.sine(amplitude, freq))
    n.R("Rg", "src", "ue", rg)
    n.C("CB", "ue", "x", cb)
    n.R("RB2", "x", "b", rb2)
    n.Q("Q1", c="col", b="b", e="0", model=model)
    n.R("RB1", "col", "b", rb1)
    n.C("CH", "col", "b", ch)
    n.R("RC", "vcc", "col", rc)
    n.C("CC", "col", "ua", cc)
    n.R("RL", "ua", "0", rl)
    n.VB("V2", "vcc", "0", _n(vcc))
    return n


def inverting_amplifier(gain=10, r1="10k", rl="10k", supply=15, model="LM741", amplitude=0.1, freq=1e3) -> Netlist:
    """Op-amp inverting stage, gain -`gain`. Nodes: in, inv, out, vcc, vee."""
    from .results import parse_value
    r1v = parse_value(r1) if isinstance(r1, str) else float(r1)
    n = Netlist()
    n.V("V1", "in", "0", sources.sine(amplitude, freq))
    n.R("R1", "in", "inv", r1)
    n.R("Rf", "out", "inv", _si(r1v * gain))
    n.OPAMP("U1", "0", "inv", "out", "vcc", "vee", model)
    n.R("RL", "out", "0", rl)
    n.VB("V2", "vcc", "0", _n(supply))
    n.VB("V3", "0", "vee", _n(supply))
    return n


def noninverting_amplifier(gain=10, rg="1k", rl="10k", supply=15, model="LM741", amplitude=0.1, freq=1e3) -> Netlist:
    """Op-amp non-inverting stage, gain 1+Rf/Rg. Nodes: in, fb, out, vcc, vee."""
    from .results import parse_value
    rgv = parse_value(rg) if isinstance(rg, str) else float(rg)
    n = Netlist()
    n.V("V1", "in", "0", sources.sine(amplitude, freq))
    n.OPAMP("U1", "in", "fb", "out", "vcc", "vee", model)
    n.R("Rf", "out", "fb", _si(rgv * (gain - 1)))
    n.R("Rg", "fb", "0", rg)
    n.R("RL", "out", "0", rl)
    n.VB("V2", "vcc", "0", _n(supply))
    n.VB("V3", "0", "vee", _n(supply))
    return n


CATALOG = {
    "voltage_divider": voltage_divider, "rc_lowpass": rc_lowpass, "rc_highpass": rc_highpass, "rlc_lowpass": rlc_lowpass,
    "diode_clipper": diode_clipper, "ce_amplifier": ce_amplifier, "ce_feedback_amplifier": ce_feedback_amplifier,
    "inverting_amplifier": inverting_amplifier, "noninverting_amplifier": noninverting_amplifier,
}
