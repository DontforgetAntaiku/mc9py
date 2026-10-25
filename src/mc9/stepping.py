"""Parameter stepping: MC9 runs the analysis several times with a component value, model parameter or temperature changed."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    """One stepped variable (MC9 allows up to 20 and runs them nested or all together)."""

    what: str                      # component name ("R1"), model name ("BF420") or a symbolic parameter
    start: str                     # first value; for method "list" the comma separated list "1k,2.2k,4.7k"
    stop: str = ""
    step: str = ""                 # increment (linear) or multiplier (log)
    param: str | None = None       # attribute / model parameter; None = MC9's default ("Value" for a component)
    method: str = "linear"         # "linear" | "log" | "list"
    kind: str = "component"        # "component" | "model" | "symbolic"
    enabled: bool = True

    def __post_init__(self):
        if self.method not in ("linear", "log", "list"):
            raise ValueError("method must be 'linear', 'log' or 'list'")
        if self.kind not in ("component", "model", "symbolic"):
            raise ValueError("kind must be 'component', 'model' or 'symbolic'")
        if self.method != "list" and not (self.stop and self.step):
            raise ValueError("a linear/log step needs start, stop and step")
