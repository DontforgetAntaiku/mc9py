"""mc9 - scripting layer for Micro-Cap 9.

    import mc9
    c = mc9.open("lab/lr2.cir")
    r = c.ac(1, 2e7)
    c.shot("fig.png")
"""
from . import library, measure, sources  # noqa: F401
from .api import OP, Circuit, Result, Run, attach, close_all, open  # noqa: F401
from .config import config  # noqa: F401
from .netlist import Netlist  # noqa: F401
from .schematic import Schematic  # noqa: F401
from .workspace import exchange as exchange_dir  # noqa: F401

__version__ = "0.3.0"
