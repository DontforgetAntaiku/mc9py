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
