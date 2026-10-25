import pytest

from mc9 import sources
from mc9.schematic import Schematic

pytestmark = pytest.mark.mc9


def test_divider_op_and_screenshot():
    s = Schematic()
    v = s.add("V", "V1", "DC 10", at=(0, 8), rot=3)
    r1 = s.add("R", "R1", "1k", at=(10, 2))
    r2 = s.add("R", "R2", "2k", at=(26, 2), rot=1)
    g = s.add("GND", None, at=(26, 14))
    s.wire(v.Plus, r1.Minus)
    s.wire(r1.Plus, r2.Minus)
    s.wire(r2.Plus, g.PinA)
    s.wire(v.Minus, (0, 14))
    s.wire((0, 14), g.PinA)
    s.node("Out", r1.Plus)
    c = s.build("it_divider", labels="dc")
    try:
        op = c.op()
        assert op.v("Out") == pytest.approx(6.667, abs=1e-3) and op.v("1") == pytest.approx(10, abs=1e-6)
        c.dynamic_dc(25)
        assert c.shot("it_divider.png", "schematic").stat().st_size > 2000
    finally:
        c.close()


def test_ac_gain_of_rc_filter():
    s = Schematic()
    v = s.add("V", "V1", sources.sine(1, 1e3), at=(0, 8), rot=3)
    r = s.add("R", "R1", "1k", at=(10, 2))
    cap = s.add("C", "C1", "159.155n", at=(26, 2), rot=1)
    g = s.add("GND", None, at=(26, 14))
    s.wire(v.Plus, r.Minus)
    s.wire(r.Plus, cap.Minus)
    s.wire(cap.Plus, g.PinA)
    s.wire(v.Minus, (0, 14))
    s.wire((0, 14), g.PinA)
    s.node("Out", r.Plus)
    c = s.build("it_rc", labels="off")
    try:
        res = c.ac(10, 1e5, 401, ["db(v(Out))"])
        assert res.value_at("db(v(Out))", 1000) == pytest.approx(-3.01, abs=0.05)  # fc = 1/(2*pi*R*C) = 1 kHz
    finally:
        c.close()


def test_autoplaced_ce_amplifier_matches_hand_calculation():
    from mc9 import library

    c = library.ce_amplifier().build("it_ce", labels="dc")
    try:
        q = c.op()["Q1"]
        assert q["VCE"] == pytest.approx(9.5, abs=0.01)
        assert q["VBE"] == pytest.approx(0.695, abs=0.002)
        assert q["IC"] == pytest.approx(7.09e-3, rel=0.01)
    finally:
        c.close()


def test_inverting_amplifier_gain_is_20_db():
    from mc9 import library

    c = library.inverting_amplifier(gain=10).build("it_inv", labels="dc", chars=7)
    try:
        r = c.ac(100, 1e5, 201, ["db(v(out)/v(in))"])
        assert r.value_at("db(v(out)/v(in))", 1000) == pytest.approx(20.0, abs=0.05)
    finally:
        c.close()


def _rc():
    from mc9 import library
    return library.rc_lowpass().build("it_rc")


def test_stepping_runs_and_parameters():
    c = _rc()
    try:
        c.step("R1", "1k", "3k", "1k", analysis="ac")
        r = c.ac(10, 1e5, 201, ["db(v(out))"])
        assert [round(run.params["R1"]) for run in r.runs] == [1000, 2000, 3000]
        f3db = [run.cross("db(v(out))", -3.0103)[0] for run in r.runs]
        assert f3db[0] == pytest.approx(1000, rel=0.02) and f3db[2] == pytest.approx(333, rel=0.02)
    finally:
        c.close()


def test_temperature_list_and_monte_carlo():
    c = _rc()
    try:
        r = c.dc("V1", 0, 1, 0.5, curves=["v(out)"], temp=[0, 25, 75])
        assert [run.params["Temperature"] for run in r.runs] == [0, 25, 75]
        c.tolerance("R1", lot="10%")
        c.monte_carlo(runs=4, seed=1, analysis="dc")
        r = c.dc("V1", 0, 1, 0.5, curves=["v(out)"], temp=25)       # the temperature list is a sticky setting
        assert len(r.runs) == 4
        r = c.dc("V1", 0, 1, 0.5, curves=["v(out)"], temp=[0, 75])  # temperatures x Monte Carlo cases
        assert len(r.runs) == 8
    finally:
        c.close()


def test_optimizer_needs_native(engine):
    if engine != "native":
        pytest.skip("the optimizer is driven through the DLL")
    c = _rc()
    try:
        res = c.optimize({"R1": (100, 5000)}, [("equals", "Y_Level(db(v(out)),1,1,2000)", -3.0103)], analysis="ac")
        assert float(res["params"]["R1"]["value"]) == pytest.approx(500, rel=0.01)
    finally:
        c.close()


def test_new_parts_simulate(engine):
    """Parts that are not in the built-in set: fetched from MC9, auto-placed, and they simulate."""
    from mc9 import Netlist, sources

    n = Netlist()
    n.V("V1", "in", "0", "DC 5")
    n.R("R1", "in", "out", "1k")
    n.R("R2", "out", "0", "1k")
    n.add("VofV", "E1", ["x", "0", "out", "0"], "10")       # a part with four pins, drawn beside the circuit and joined by name
    n.R("RL", "x", "0", "10k")
    c = n.build("it_vofv", labels="dc")
    try:
        op = c.op()
        assert op.v("out") == pytest.approx(2.5, abs=1e-3) and op.v("x") == pytest.approx(25.0, abs=1e-2)
    finally:
        c.close()

    j = Netlist()
    j.V("V1", "in", "0", sources.sine(0.1, 1e3))
    j.C("C1", "in", "g", "1u")
    j.R("RG", "g", "0", "1Meg")
    j.J("J1", "d", "g", "s", "J111")
    j.R("RD", "vdd", "d", "4.7k")
    j.R("RS", "s", "0", "1k")
    j.VB("V2", "vdd", "0", "12")
    c = j.build("it_jfet", labels="dc")
    try:
        assert c.op()["J1"]["ID"] == pytest.approx(2.04e-3, rel=0.02)
    finally:
        c.close()
