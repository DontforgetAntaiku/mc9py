import pytest

from mc9 import library
from mc9.netlist import GROUND

NAMES = list(library.CATALOG)


def netlist_classes(nl):
    cls = {}
    for p in nl.parts:
        for pin, net in p.nets.items():
            cls.setdefault("0" if net in GROUND else net, set()).add((p.name, pin))
    return {frozenset(v) for v in cls.values()}


def schematic_classes(sch):
    cls = {}
    for key, nid in sch.pin_nets().items():
        cls.setdefault(nid, set()).add(key)
    return {frozenset(v) for v in cls.values()}


@pytest.mark.parametrize("name", NAMES)
def test_autoplace_is_electrically_identical_and_clean(name):
    nl = library.CATALOG[name]()
    sch = nl.schematic()
    assert sch.check() == [], sch.check()
    assert sch.audit("dc") == [], sch.audit("dc")
    assert sch.notes == []
    assert schematic_classes(sch) == netlist_classes(nl)  # same nets, whatever the drawing looks like


@pytest.mark.parametrize("name", ["voltage_divider", "ce_amplifier", "inverting_amplifier"])
def test_ac_mode_leaves_room_for_phasor_boxes(name):
    sch = library.CATALOG[name]().schematic(mode="ac")
    assert sch.audit("ac") == []
    assert schematic_classes(sch) == netlist_classes(library.CATALOG[name]())


def test_every_part_is_placed_once():
    nl = library.ce_feedback_amplifier()
    sch = nl.schematic()
    names = sorted(p.name for p in sch.parts if p.name)
    assert names == sorted(p.name for p in nl.parts)


def test_every_netlist_helper_returns_its_part():
    from mc9 import Netlist

    n = Netlist()
    parts = [
        n.R("R1", "a", "0", "1k"),
        n.C("C1", "a", "0", "1n"),
        n.L("L1", "a", "0", "1m"),
        n.V("V1", "a", "0", "DC 1"),
        n.VB("V2", "a", "0", "5"),
        n.I("I1", "a", "0", "1m"),
        n.D("D1", "a", "0"),
        n.Q("Q1", "a", "b", "0", "BF420"),
        n.QP("Q2", "a", "b", "0", "BC557"),
        n.M("M1", "a", "b", "0", "0", "2N7000"),
        n.OPAMP("U1", "a", "b", "c", "d", "e"),
    ]
    assert all(p is not None and p.name for p in parts)
    assert [p.name for p in n.parts] == [p.name for p in parts]
