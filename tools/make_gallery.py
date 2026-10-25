"""Produce the pictures used in README / docs (docs/assets/*.png) with a real MC9. Developers only.

python tools/make_gallery.py            # everything (~10 min)
python tools/make_gallery.py ce clip    # selected sections: ce, inv, clip
"""

import shutil
import sys
import warnings
from pathlib import Path

from mc9 import library, measure

OUT = Path(__file__).resolve().parents[1] / "docs" / "assets"
OUT.mkdir(parents=True, exist_ok=True)
warnings.simplefilter("ignore")
ONLY = set(sys.argv[1:]) or {"ce", "inv", "clip"}


def save(path, name):
    shutil.copyfile(path, OUT / name)
    print("  ->", OUT / name, flush=True)


def ce():
    """Common-emitter amplifier: schematic with voltages and phasors, AC plot with cursors, transient, distortion."""
    c = library.ce_amplifier().build("g_ce", labels="ac")
    try:
        c.dynamic_dc(25)
        save(c.shot("g1.png", "schematic"), "ce_schematic_dc.png")
        c.dynamic_ac(2224)
        save(c.shot("g2.png", "schematic"), "ce_schematic_ac.png")
        bw = measure.bandwidth(c, "db(v(ua)/v(ue))", cursors=True)
        print(f"  CE band: {bw.g0_db:.2f} dB, {bw.f_low:.1f} Hz .. {bw.f_high:.0f} Hz")
        save(c.shot("g3.png"), "ce_ac_cursors.png")
        c.transient(10e-3, 8e-3, points=1001, curves=["v(ue)", "v(ua)"])
        save(c.shot("g4.png"), "ce_transient.png")
        c.distortion(2224, "V1", 35e-3, "v(ua)")
        save(c.shot("g5.png"), "ce_distortion.png")
    finally:
        c.close()


def inv():
    """Inverting op-amp stage."""
    c = library.inverting_amplifier().build("g_inv", labels="dc", chars=7)
    try:
        c.dynamic_dc(25)
        save(c.shot("g6.png", "schematic"), "inverting_schematic.png")
    finally:
        c.close()


def clip():
    """Diode clipper, transient."""
    c = library.diode_clipper().build("g_clip", labels="dc")
    try:
        c.transient(3e-3, 1e-3, points=1001, curves=["v(in)", "v(out)"])
        save(c.shot("g7.png"), "clipper_transient.png")
    finally:
        c.close()


for name, fn in (("ce", ce), ("inv", inv), ("clip", clip)):
    if name in ONLY:
        fn()
print("done")
