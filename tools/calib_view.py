"""Does [Page] Grid= control the viewport? Place a marker resistor at known grid coords and see where it lands."""

import numpy as np
from PIL import Image
import mc9
from mc9.schematic import Schematic
from mc9 import workspace

for pg in ("0,540", "400,100", "200,300"):
    s = Schematic()
    s.add("R", "R1", "1k", at=(50, 80))
    c = s.to_cir(shift=(0, 0))
    page = next(x for x in c.sections if x.name == "Page")
    page.set("SB 3", pg)
    c.save(str(workspace.path("calib3")))
    cc = mc9.attach("calib3")
    cc.close()
    cc = mc9.attach("calib3")
    m = cc._session()
    m.s.cmd("k Escape")
    m.click((213, 94), 0.5)
    m.click((420, 860), 0.5)
    m.s.cmd("mv 1960 1090")
    m.s.cmd("s 1")
    m.s.cmd("shot calib3_raw.png")
    cc.close()
    im = np.array(Image.open(workspace.exchange() / "calib3_raw.png").convert("RGB")).astype(int)[112:905, 205:1870]
    blue = (im[..., 2] > 200) & (im[..., 0] < 60) & (im[..., 1] < 60)
    ys, xs = np.nonzero(blue)
    print(
        f"SB 3={pg}: marker R1 grid(50,80) found at px x={xs.min() + 205 if len(xs) else None} y={ys.min() + 112 if len(ys) else None}",
        flush=True,
    )
