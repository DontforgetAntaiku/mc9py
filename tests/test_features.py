"""Stepping, tolerances, Monte Carlo and model text are written to the .cir exactly as MC9 itself writes them."""
import pytest

from mc9 import library
from mc9.cir import Cir


@pytest.fixture
def circ(tmp_path, monkeypatch):
    monkeypatch.setenv("MC9_HOME", str(tmp_path))
    return library.rc_lowpass().build("feat_t")


def sections(c, name, analysis):
    return [dict(ln.split("=", 1) for ln in s.lines if "=" in ln) for s in c._cir.sections
            if s.name == name and (s.get("Analysis") or "").lower() == analysis.lower()]


def test_linear_log_and_list_steps(circ):
    circ.step("R1", "1k", "3k", "1k", analysis="transient")
    circ.step("C1", "100n,159n", analysis="transient")
    circ.step("R1", 100, 1e5, 10, method="log", analysis="ac")
    circ._flush()
    tr = sections(circ, "Stepping", "Transient")
    assert [s["Index"] for s in tr] == ["1", "2"]
    assert tr[0] == {"Analysis": "Transient", "Index": "1", "Status": "On", "Parameter Type": "Component", "Name": "R1",
                     "Param": "Value", "From": "1k", "To": "3k", "Value": "1k"}
    assert tr[1]["Method"] == "List" and tr[1]["From"] == "100n,159n" and "To" not in tr[1]
    ac = sections(circ, "Stepping", "AC")
    assert ac[0]["Method"] == "Log" and ac[0]["Value"] == "10"
    assert not sections(circ, "Stepping", "DC")


def test_simultaneous_and_clear(circ):
    circ.step("R1", "1k", "2k", "1k", analysis="dc")
    circ.step("C1", "1n", "2n", "1n", analysis="dc")
    circ.stepping_mode(False)
    circ._flush()
    assert sections(circ, "Stepping", "DC")[0]["Simultaneous"] == "Yes"
    circ.clear_steps()
    circ._flush()
    assert not sections(circ, "Stepping", "DC")


def test_model_step_and_roundtrip(circ, tmp_path):
    circ.step("BF420", 100, 400, 100, param="BF", kind="model", analysis="transient")
    circ._flush()
    s = sections(circ, "Stepping", "Transient")[0]
    assert (s["Parameter Type"], s["Name"], s["Param"]) == ("Model", "BF420", "BF")
    assert Cir.load(str(circ.path)).stepping("transient")[0]["Name"] == "BF420"


def test_tolerance_writes_model_text_and_attribute(circ):
    circ.tolerance("R1", lot="10%", dev=2)
    cir = circ._cir
    text = next(s for s in cir.sections if s.name == "Text Area" and s.get("Page") == "1")
    body = [ln for ln in text.lines[text.lines.index("") + 1:] if ln]
    assert body == [".MODEL R1_TOL RES (R=1 LOT=10% DEV=2% )"]
    assert int(text.get("Len")) == len(body[0]) + 2          # MC9 reads exactly Len-2 characters
    assert cir.find_part("R1")["attrs"]["MODEL"] == "R1_TOL"
    circ.tolerance("R1", lot=5)                              # again: the model line is replaced, not duplicated
    body = [ln for ln in text.lines[text.lines.index("") + 1:] if ln]
    assert body == [".MODEL R1_TOL RES (R=1 LOT=5% )"]
    assert sum(1 for c in cir.components() if c["attrs"].get("PART") == "R1") == 1


def test_monte_carlo_options(circ):
    circ.monte_carlo(runs=25, distribution="worst case", seed=3, analysis=["transient", "ac"])
    m = circ._cir.monte_carlo("Transient")
    assert (m.get("Status"), m.get("Number of Runs"), m.get("Distribution"), m.get("Seed")) == ("On", "25", "Worst Case", "3")
    assert circ._cir.monte_carlo("DC").get("Status") == "Off"
    with pytest.raises(ValueError):
        circ.monte_carlo(distribution="triangular")


def test_tolerance_rejects_active_parts(circ):
    with pytest.raises(ValueError):
        circ.tolerance("V1", lot="5%")


def test_stepped_run_labels_and_select():
    from pathlib import Path

    from mc9.api import Result
    r = Result("transient", str(Path(__file__).parent / "data" / "stepped.TNO"))
    assert len(r.runs) == 2
    assert r.runs[0].params == {"Temperature": 25.0, "R1": 1000.0}
    assert r.select(R1=2000)[0]["v(out)"] == [0.3, 0.4]
    assert r.select(R1=9999) == []
