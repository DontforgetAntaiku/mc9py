"""Regenerate src/mc9/templates/base.cir (developers only).

The template carries the analysis/window setup of a normal MC9 circuit plus a catalog of component definitions harvested from
MC9's own sample circuits. Usage:

    python tools/make_base.py --mc9 "/path/to/MC9 install dir" --base /path/to/any_circuit_with_all_analyses.cir

Personal data (circuit/section name, licence 'Key ID') is stripped. Run `pytest` afterwards and, with MC9 available,
`MC9_INTEGRATION=1 pytest tests/test_integration.py`.
"""

import argparse
import glob
from pathlib import Path

from mc9 import cir

WANT = [
    "Resistor",
    "Capacitor",
    "Inductor",
    "Battery",
    "Voltage Source",
    "Current Source",
    "Ground",
    "Diode",
    "NPN",
    "PNP",
    "Opamp",
    "NMOS",
]


def shape_closure(c, name, out, seen):
    for s in c.sections:
        if s.name == "shapedef" and s.get("Name") == name and name not in seen:
            seen.add(name)
            out.append(s)
            for ln in s.lines:
                if ln.startswith("Root="):
                    shape_closure(c, ln.split('"')[1], out, seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc9", required=True, help="MC9 install directory (contains DATA/*.cir)")
    ap.add_argument("--base", required=True, help="a circuit saved by MC9 that has transient/AC/DC/distortion windows")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "src/mc9/templates/base.cir"))
    a = ap.parse_args()

    base = cir.Cir.load(a.base)
    have = {s.get("Name") for s in base.sections if s.name == "compdef"}
    have_shapes = {s.get("Name") for s in base.sections if s.name == "shapedef"}
    files = sorted(glob.glob(a.mc9 + "/DATA/*.cir") + glob.glob(a.mc9 + "/DATA/*.CIR"))
    new_shapes, new_comps = [], []
    for want in WANT:
        if want in have:
            continue
        for f in files:
            try:
                c = cir.Cir.load(f)
            except Exception:
                continue
            cd = next((s for s in c.sections if s.name == "compdef" and s.get("Name") == want), None)
            if cd is None:
                continue
            shapes, seen = [], have_shapes | {s.get("Name") for s in new_shapes}
            shape_closure(c, cd.get("Shape"), shapes, seen)
            new_shapes += shapes
            new_comps.append(cd)
            have.add(want)
            print("harvested", want, "from", Path(f).name)
            break
        else:
            print("NOT FOUND", want)

    secs = [s for s in base.sections if s.name not in ("Comp", "Attr", "Wire", "Grid Text", "Text Area")]
    first = next(i for i, s in enumerate(secs) if s.name == "compdef")
    secs[first:first] = new_shapes
    last = max(i for i, s in enumerate(secs) if s.name == "compdef")
    secs[last + 1 : last + 1] = new_comps
    base.sections = secs
    main_sec = base.sections[0]
    main_sec.set("NLCnt", "0")
    main_sec.set("TXCnt", "0")
    main_sec.lines[:] = [ln for ln in main_sec.lines if not ln.startswith("Key ID")]  # licence identifier
    for s in base.sections:
        if s.name == "Section":
            s.set("Name", '"circuit"')  # was the author's file name
    circ = next(s for s in base.sections if s.name == "Circuit")
    for k, v in {"Show Voltages": "True", "Show Current": "False", "Show Power": "False", "Show Nodes": "False"}.items():
        circ.set(k, v)
    base.save(a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
