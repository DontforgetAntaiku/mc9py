"""Auto-placement gallery: every starter circuit is placed, built, simulated and photographed by MC9.

python examples/netlist_gallery.py                 # all of them
python examples/netlist_gallery.py ce_amplifier    # one
"""

import sys
import warnings

from mc9 import library

names = sys.argv[1:] or list(library.CATALOG)
for name in names:
    nl = library.CATALOG[name]()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        c = nl.build(f"auto_{name}", labels="dc")
    print(f"== {name}: {[str(x.message)[:100] for x in w]}", flush=True)
    try:
        op = c.op()
        print("   operating point:", {k: round(v, 4) for k, v in op.nodes.items()}, flush=True)
        c.dynamic_dc(25)
        print("  ", c.shot(f"auto_{name}.png", "schematic"), flush=True)
    finally:
        c.close()
