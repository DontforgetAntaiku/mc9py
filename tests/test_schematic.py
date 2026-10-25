import pytest

from mc9.schematic import Schematic


def divider(spacing=10):
    s = Schematic()
    v = s.add("V", "V1", "DC 10", at=(0, 8), rot=3)
    r1 = s.add("R", "R1", "1k", at=(spacing, 2))
    r2 = s.add("R", "R2", "2k", at=(spacing + 16, 2), rot=1)
    g = s.add("GND", None, at=(spacing + 16, 14))
    s.wire(v.Plus, r1.Minus)
    s.wire(r1.Plus, r2.Minus)
    s.wire(r2.Plus, g.PinA)
    s.wire(v.Minus, (0, 14))
    s.wire((0, 14), g.PinA)
    return s


def test_rotation_and_pin_positions():
    s = Schematic()
    r = s.add("R", "R1", "1k", at=(10, 10))
    assert r.Minus == (10, 10) and r.Plus == (16, 10)
    assert s.add("R", "R2", "1k", at=(10, 10), rot=1).Plus == (10, 16)
    assert s.add("R", "R3", "1k", at=(10, 10), rot=2).Plus == (4, 10)
    assert s.add("R", "R4", "1k", at=(10, 10), rot=3).Plus == (10, 4)
    q = s.add("Q", "Q1", at=(10, 10), MODEL="BF420")
    assert q.Base == (10, 10) and q.Collector == (13, 7) and q.Emitter == (13, 13)
    assert q.kind.value_attr == "MODEL" and q.value == "BF420"


def test_unknown_kind_and_duplicate_model():
    s = Schematic()
    with pytest.raises(KeyError):
        s.add("FOO", "X1")
    with pytest.raises(ValueError):
        s.add("Q", "Q1", "BF420", MODEL="BF420")


def test_t_junction_split_and_check_clean():
    s = divider()
    assert s.check() == []
    segs = s._split_wires()
    assert all(a != c or b != d for a, b, c, d in segs)
    cir = s.to_cir()
    wires = [x for x in cir.sections if x.name == "Wire"]
    assert len(wires) >= 5 and int(cir.sections[0].get("NLCnt")) == 0


def test_unwired_pin_and_missing_dc_path_are_reported():
    s = Schematic()
    v = s.add("V", "V1", "DC 5", at=(0, 8), rot=3)
    c = s.add("C", "C1", "1u", at=(6, 2))
    g = s.add("GND", None, at=(0, 14))
    s.wire(v.Plus, c.Minus)
    s.wire(v.Minus, g.PinA)  # C1.Plus floats; load only via a capacitor
    issues = s.check()
    assert any("C1.Plus" in m and "not wired" in m for m in issues)
    assert any("no DC path" in m for m in issues)


def test_crossing_wires_without_junction_are_flagged():
    s = divider()
    s.wire((5, 0), (5, 12))  # crosses the horizontal wire at y=2? make a real crossing
    s.wire((2, 5), (9, 5))
    assert any("cross" in m for m in s.check())


def test_auto_labels_have_no_collisions_when_spaced():
    s = divider(spacing=12)
    s.node("Out", s.parts[1].Plus)
    s.auto_labels("dc")
    assert s.notes == []
    assert s.audit("dc") == []


def test_audit_reports_cramped_ac_boxes():
    s = divider(spacing=0)  # two nodes only 6 grid units apart: 190 px phasor boxes collide
    s.node("Out", s.parts[1].Plus)
    s.auto_labels("ac")
    assert any("voltage box" in m for m in s.audit("ac"))


def test_zoom_snaps_and_crop_inside_canvas():
    s = divider()
    s.auto_labels("dc")
    s.to_cir()
    assert s.zoom == 2.0 and s.crop_px[0] >= 200 and s.crop_px[2] <= 1900
    wide = Schematic()
    wide.add("R", "R1", "1k", at=(0, 0))
    wide.add("R", "R2", "1k", at=(130, 0))
    wide.to_cir()
    assert wide.zoom == 1.0


def test_source_strings():
    from mc9 import sources

    assert sources.sine(0.01, 1000, ac=0.01) == "DC 0 AC 0.01 0 Sin 0 0.01 1000 0 0 0"
    assert sources.pulse(-1, 1, 1e-3).startswith("DC 0 AC 1 0 Pulse -1 1 0 1e-09 1e-09")


def test_audit_flags_node_name_on_a_body():
    s = divider(spacing=12)
    s.node("Out", s.parts[1].Minus)  # right at R1's first zigzag
    assert any("node name 'Out' overlaps body of R1" in m for m in s.audit("dc"))


def test_node_name_in_wire_interior_splits_the_wire():
    s = divider(spacing=12)
    s.node("Mid", (16, 2))  # R1 spans (12..18, 2); wire R1.Plus -> R2.Minus is 18..28
    s.node("W", (22, 2))  # interior of the R1.Plus -> R2.Minus wire
    ends = {(a, b) for a, b, c, d in s._split_wires()} | {(c, d) for a, b, c, d in s._split_wires()}
    assert (22, 2) in ends


def test_unknown_node_label_in_curve_is_warned(tmp_path, monkeypatch):
    import warnings
    from mc9 import api, workspace

    monkeypatch.setattr(workspace, "exchange", lambda: tmp_path)
    s = divider(spacing=12)
    s.node("Out", s.parts[1].Plus)
    s.to_cir().save(str(tmp_path / "t.cir"))
    c = api.Circuit("t")
    c.curves("ac", "db(v(Out))", "db(v(Nope))", "i(R1)")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        c._check_expressions("ac")
    msgs = " ".join(str(x.message) for x in w)
    assert "Nope" in msgs and "'Out'" not in msgs and "'R1'" not in msgs


def test_wire_through_a_part_body_is_flagged():
    s = divider(spacing=12)
    s.wire((15, -3), (15, 6))  # R1 spans x 12..18 at y=2: this wire cuts through its middle
    assert any("runs through the body of R1" in m for m in s.check())


def test_supply_is_placed_beyond_the_whole_circuit():
    from mc9 import library

    sch = library.ce_amplifier().schematic()
    supply = next(p for p in sch.parts if p.name == "V2")
    others = [max(a, c) for a, b, c, d in sch.segments]
    assert supply.at[0] >= sorted(others)[-3]  # at (or beyond) the right end of the drawing
    assert not any("through the body" in m for m in sch.check())
