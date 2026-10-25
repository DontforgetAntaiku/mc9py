"""Quick look at any MC9 circuit file: parts, operating point, AC response (if it has an AC curve), screenshots.

    python examples/analyze_cir.py path/to/circuit.cir "db(v(out)/v(in))"

The file is copied into the work folder; the original is never modified.
"""

import sys

import mc9
from mc9 import measure

path = sys.argv[1]
curve = sys.argv[2] if len(sys.argv) > 2 else None

with mc9.open(path) as c:
    print("parts:")
    for name, info in c.parts().items():
        print(f"  {name:6s} {info}")
    op = c.op()
    print("operating point:", {k: round(v, 5) for k, v in op.nodes.items()})
    c.dynamic_dc(25)
    print("schematic:", c.shot("overview.png", "schematic"))
    if curve:
        r = c.ac(1, 1e7, 401, [curve])
        try:
            bw = measure.bandwidth(c, curve, cursors=True)
            print(f"gain {bw.g0_db:.2f} dB at {bw.f0:.1f} Hz, band {bw.f_low} .. {bw.f_high} Hz")
        except RuntimeError as e:
            print("bandwidth:", e)
        print("AC plot:", c.shot("ac.png"))
