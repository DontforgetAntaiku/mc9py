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
