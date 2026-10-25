import math

import pytest

from mc9 import catalog, cir, results

SAMPLE_TNO = """
DC Operating Point Voltages
===========================
Node         Voltage  Node         Voltage
1           351.266u  UE          351.266u
3            695.354m  UA            0.000


Operating point for devices of type Resistor
============================================
Instance:                  R1              R3
DC Power Terms:
PD                     0.000          60.202m

DC Pin Currents:
Ir                     0.000          -7.083m


Waveform Values
===============
           F db(v(Ua)/v(Ue)) ph(v(Ua)/v(Ue))
        (Hz)                       (Degrees)
       1.000         -38.538             N/A
       1.043         -37.807          -1.303
       2.000          12.000K       -90.000
"""


def test_parse_value_suffixes():
    pv = results.parse_value
    assert pv("1.5K") == 1500 and pv("4.7u") == 4.7e-6 and pv("2MEG") == 2e6 and pv("-3m") == -3e-3
    assert pv("1e3") == 1000 and math.isnan(pv("N/A")) and pv("abc") is None


def test_waveforms_with_na_first_row():
    t = results.parse_waveforms(SAMPLE_TNO)[0]
    assert t["columns"] == ["F", "db(v(Ua)/v(Ue))", "ph(v(Ua)/v(Ue))"]
    assert len(t["rows"]) == 3 and math.isnan(t["rows"][0][2]) and t["rows"][2][1] == 12000


def test_operating_point():
    op = results.parse_op(SAMPLE_TNO)
    assert op["nodes"]["3"] == pytest.approx(0.695354)
    assert op["devices"]["R3"]["PD"] == pytest.approx(0.060202) and op["devices"]["R3"]["Ir"] == pytest.approx(-0.007083)


def test_cir_roundtrip_and_edit(tmp_path):
    c = cir.Cir.load(str(catalog.BASE))
    assert "Resistor" in {k for k in catalog.load()}
    c.sections.insert(5, cir.Section("Comp", ["Name=Resistor", "Grid=1,1", "Rot=0"]))
    c.sections.insert(6, cir.Section("Attr", ["ONV=0,0,PART,R9", "Style=8192"]))
    c.sections.insert(7, cir.Section("Attr", ["ONV=0,0,RESISTANCE,1k", "Style=8192"]))
    assert c.set_attr("R9", "resistance", "4.7k") == "1k"
    assert c.find_part("R9")["attrs"]["RESISTANCE"] == "4.7k"
    p = tmp_path / "x.cir"
    c.save(str(p))
    assert cir.Cir.load(str(p)).dumps() == c.dumps()


def test_waveforms_and_output_flag():
    c = cir.Cir.load(str(catalog.BASE))
    c.set_waveforms("AC", [{"y": "db(v(1))"}, {"y": "ph(v(1))", "plot": 2}])
    c.enable_output("AC")
    wf = c.waveforms("AC")
    assert [w["y"] for w in wf] == ["db(v(1))", "ph(v(1))"] and all("OUTPUT" in w["options"] for w in wf)
