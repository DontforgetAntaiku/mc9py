import math

import pytest
from tests_helpers import netlist_classes, schematic_classes

from mc9 import audio


@pytest.fixture
def specs():
    return audio.Specs(p_out=24, r_load=6, r_in=60e3, f_low=25, f_high=18e3, thd=0.3)


def test_derived_numbers(specs):
    assert specs.v_out == pytest.approx(math.sqrt(2 * 24 * 6))
    assert specs.i_out == pytest.approx(specs.v_out / 6)
    assert specs.gain == pytest.approx(specs.v_out / specs.u_in)
    assert specs.vcc > specs.v_out + 3
    assert 0.5 < specs.xi < 0.95 and 0.4 < specs.efficiency < 0.785
    assert specs.p_dissipation_max == pytest.approx(2 * specs.vcc ** 2 / (math.pi ** 2 * 6))


@pytest.mark.parametrize("p,rl", [(10, 8), (24, 6), (100, 3)])
def test_drawing_matches_the_netlist(p, rl):
    s = audio.Specs(p_out=p, r_load=rl, r_in=20e3, f_low=30, f_high=20e3)
    sch = audio.schematic(s)
    assert sch.check() == [], sch.check()
    assert schematic_classes(sch) == netlist_classes(audio.power_amplifier(s))


def test_edge_time_of_an_rc_step():
    import math
    tau = 1e-6
    t = [i * 1e-8 for i in range(3000)]
    up = [1 - math.exp(-x / tau) for x in t]
    # 10 % -> 90 % of an RC step takes tau * ln 9
    assert audio.edge_time(t, up, 0.1, 0.9) == pytest.approx(tau * math.log(9), rel=1e-3)
    down = [math.exp(-x / tau) for x in t]
    assert audio.edge_time(t, down, 0.9, 0.1) == pytest.approx(tau * math.log(9), rel=1e-3)
    assert audio.edge_time(t, up, 2.0, 3.0) is None


def test_phase_margin_estimate():
    assert audio.phase_margin_from_peaking(0.0) is None
    assert 40 < audio.phase_margin_from_peaking(1.0) < 80
    assert audio.phase_margin_from_peaking(6.0) < audio.phase_margin_from_peaking(1.0)
