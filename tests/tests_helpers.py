from mc9.netlist import GROUND


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
