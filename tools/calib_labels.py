"""Calibrate MC9 label geometry: place resistors with known label offsets, measure where text lands."""

import numpy as np
from scipy import ndimage
from PIL import Image
import mc9
from mc9.schematic import Schematic
from mc9 import workspace

s = Schematic()
for i, rot in enumerate((0, 1, 2, 3)):
    s.add("Resistor", f"R{i}", "1k", (30 + 20 * i, 90), rot=rot, attr="RESISTANCE", part_label=(0, 0), value_label=(0, 40))
s.save(str(workspace.path("calib")))
with mc9.attach("calib") as c:
    m = c._session()
    m.s.cmd("k Escape")
    m.click((213, 94), 0.5)
    m.click((420, 860), 0.5)
    m.s.cmd("mv 1960 1090")
    m.s.cmd("s 1")
    m.s.cmd("shot calib_raw.png")
im = np.array(Image.open(workspace.exchange() / "calib_raw.png").convert("RGB")).astype(int)
sub = im[112:905, 205:1870]


def comps(mask, label):
    lab, n = ndimage.label(ndimage.binary_dilation(mask, iterations=3))
    out = []
    for sl in ndimage.find_objects(lab):
        ys, xs = sl
        out.append((xs.start + 205 + 3, ys.start + 112 + 3, xs.stop + 205 - 3, ys.stop + 112 - 3))
    print(label, sorted(out))


green = (abs(sub[..., 0] - 0) < 40) & (abs(sub[..., 1] - 128) < 40) & (abs(sub[..., 2] - 0) < 40)
blue = (sub[..., 2] > 200) & (sub[..., 0] < 60) & (sub[..., 1] < 60)
comps(green, "green text")
comps(blue, "blue symbols")
