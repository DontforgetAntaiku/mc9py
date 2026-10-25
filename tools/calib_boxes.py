"""Where does MC9 draw Dynamic-DC voltage boxes relative to each pin?"""

import numpy as np
from scipy import ndimage
from PIL import Image
import mc9
from mc9.schematic import Schematic
from mc9 import workspace

X0, Y0, U = 201, -970, 16  # pixel = X0 + U*gx ; Y0 + U*gy   (measured)
s = Schematic()
v1 = s.add("Voltage Source", "V1", "DC 10", (30, 100), rot=3)
r1 = s.add("Resistor", "R1", "1k", (36, 94), rot=0, attr="RESISTANCE")
r2 = s.add("Resistor", "R2", "2k", (50, 94), rot=1, attr="RESISTANCE")
r3 = s.add("Resistor", "R3", "3k", (60, 100), rot=2, attr="RESISTANCE") if False else None
g = s.add("Ground", None, None, (50, 108))
s.wire(v1.Plus, r1.Minus)
s.wire(r1.Plus, r2.Minus)
s.wire(r2.Plus, g.PinA)
s.wire(v1.Minus, g.PinA, via="v")
s.save(str(workspace.path("calib2")))
pins = {
    "V1.Plus": v1.Plus,
    "V1.Minus": v1.Minus,
    "R1.Minus": r1.Minus,
    "R1.Plus": r1.Plus,
    "R2.Minus": r2.Minus,
    "R2.Plus": r2.Plus,
}
with mc9.attach("calib2") as c:
    c.dynamic_dc(25)
    m = c._session()
    m.s.cmd("k Escape")
    m.click((213, 94), 0.5)
    m.click((420, 860), 0.5)
    m.s.cmd("mv 1960 1090")
    m.s.cmd("s 1")
    m.s.cmd("shot calib2_raw.png")
im = np.array(Image.open(workspace.exchange() / "calib2_raw.png").convert("RGB")).astype(int)
sub = im[112:905, 205:1870]
mag = (sub[..., 0] > 200) & (sub[..., 1] < 80) & (sub[..., 2] > 200)
lab, n = ndimage.label(ndimage.binary_dilation(mag, iterations=2))
boxes = [(xs.start + 205 + 2, ys.start + 112 + 2, xs.stop + 205 - 2, ys.stop + 112 - 2) for ys, xs in ndimage.find_objects(lab)]
print("boxes (x0,y0,x1,y1):", boxes)
for name, (gx, gy) in pins.items():
    px, py = X0 + U * gx, Y0 + U * gy
    near = min(boxes, key=lambda b: abs((b[0] + b[2]) / 2 - px) + abs((b[1] + b[3]) / 2 - py)) if boxes else None
    print(
        f"{name:9s} grid=({gx},{gy}) px=({px},{py}) -> nearest box rel: left={near[0] - px:+d} top={near[1] - py:+d} right={near[2] - px:+d} bottom={near[3] - py:+d}"
        if near
        else name
    )
