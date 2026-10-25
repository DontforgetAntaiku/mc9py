"""More parts in the builder: definitions MC9 wrote (tests/data/parts_sample.cir) are placed and wired like the built-in ones."""
from pathlib import Path

import pytest

from mc9 import Netlist, catalog, sources
from mc9.netlist import GROUND
from tests_helpers import netlist_classes, schematic_classes  # noqa: F401  (see conftest: tests/ is on the path)


@pytest.fixture(autouse=True)
def learned_parts(monkeypatch):
    monkeypatch.setattr(catalog, "user_file", lambda: Path(__file__).parent / "data" / "parts_sample.cir")
    catalog._CACHE = None
    yield
    catalog._CACHE = None


def jfet_stage():
    n = Netlist()
    n.V("V1", "in", "0", sources.sine(0.1, 1e3))
    n.C("C1", "in", "g", "1u")
    n.R("RG", "g", "0", "1Meg")
    n.J("J1", "d", "g", "s", "J111")
    n.R("RD", "vdd", "d", "4.7k")
    n.R("RS", "s", "0", "1k")
    n.C("C2", "d", "out", "1u")
    n.R("RL", "out", "0", "100k")
    n.VB("V2", "vdd", "0", "12")
    return n


def nmos_follower():
    n = Netlist()
    n.V("V1", "in", "0", sources.sine(0.1, 1e3))
    n.M("M1", "vdd", "in", "src", "src", "IRF540")
    n.R("RS", "src", "0", "1k")
    n.C("C1", "src", "out", "1u")
    n.R("RL", "out", "0", "10k")
    n.VB("V2", "vdd", "0", "12")
    return n


def pmos_amplifier():
    n = Netlist()
    n.V("V1", "in", "0", sources.sine(0.1, 1e3))
    n.C("C1", "in", "g", "1u")
    n.R("RG", "g", "vdd", "100k")
    n.MP("M1", "d", "g", "vdd", "vdd", "KP944B")
    n.R("RD", "d", "0", "4.7k")
    n.C("C2", "d", "out", "1u")
    n.R("RL", "out", "0", "100k")
    n.VB("V2", "vdd", "0", "12")
    return n


def zener_regulator():
    n = Netlist()
    n.V("V1", "in", "0", sources.sine(1, 1e3))
    n.R("R1", "in", "out", "470")
    n.Z("D1", "0", "out", "DZENER")          # cathode to the output
    n.C("C1", "out", "0", "10u")
    return n


@pytest.mark.parametrize("make", [jfet_stage, nmos_follower, pmos_amplifier, zener_regulator])
def test_new_parts_are_placed_and_equivalent(make):
    nl = make()
    sch = nl.schematic()
    assert sch.check() == [], sch.check()
    assert schematic_classes(sch) == netlist_classes(nl)
    assert sorted(p.name for p in sch.parts if p.name) == sorted(p.name for p in nl.parts)


def test_satellite_parts_are_connected_by_name():
    n = jfet_stage()
    n.add("Transformer", "T1", ["out", "0", "d", "0"], "1")           # four pins, not on any signal path
    n.add("VofV", "E1", ["x", "0", "out", "0"], "10")
    nl = n
    sch = nl.schematic()
    assert sch.check() == [], sch.check()
    assert schematic_classes(sch) == netlist_classes(nl)


def test_definitions_travel_with_the_circuit(tmp_path, monkeypatch):
    monkeypatch.setenv("MC9_HOME", str(tmp_path))
    nl = jfet_stage()
    cir = nl.schematic().to_cir()
    comps = {s.get("Name") for s in cir.sections if s.name == "compdef"}
    assert {"NJFET", "Resistor"} <= comps
    shapes = {s.get("Name") for s in cir.sections if s.name == "shapedef"}
    assert "NJFET" in shapes
    first_circuit = next(i for i, s in enumerate(cir.sections) if s.name == "Circuit")
    assert all(i < first_circuit for i, s in enumerate(cir.sections) if s.name == "compdef")


def test_pins_by_name_and_wrong_pin_count():
    n = Netlist()
    n.add("NJFET", "J1", {"Drain": "d", "Gate": "g", "Source": "s"}, "J111")
    assert n.parts[0].nets == {"Drain": "d", "Gate": "g", "Source": "s"}
    with pytest.raises(ValueError):
        n.add("NJFET", "J2", ["d", "g"], "J111")
    with pytest.raises(KeyError):
        n.add("NoSuchPart", "X1", ["a"], None)


def test_body_on_its_own_node():
    n = Netlist()
    n.V("V1", "in", "0", sources.sine(0.1, 1e3))
    n.M("M1", "d", "in", "s", "0", "IRF540")
    n.R("RD", "vdd", "d", "1k")
    n.R("RS", "s", "0", "100")
    n.VB("V2", "vdd", "0", "12")
    sch = n.schematic()
    assert sch.check() == [], sch.check()
    assert schematic_classes(sch) == netlist_classes(n)


def test_ground_aliases():
    assert "0" in GROUND
