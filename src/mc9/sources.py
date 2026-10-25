"""VALUE strings for MC9's SPICE-style 'Voltage Source' / 'Current Source' parts.

    s.add("V", "V1", sources.sine(0.01, 1e3, ac=0.01))     # -> 'DC 0 AC 0.01 0 Sin 0 0.01 1000 0 0 0'
    s.add("V", "V1", sources.pulse(-1, 1, 1e-3, rise=1e-9, fall=1e-9))
"""
from __future__ import annotations


def _n(v) -> str:
    return v if isinstance(v, str) else repr(float(v)) if not float(v).is_integer() else str(int(v))


def dc(value) -> str:
    return f"DC {_n(value)}"


def sine(amplitude, freq, offset=0, ac=None, dc_level=0, delay=0, damping=0, phase=0) -> str:
    """Sine source; `ac` = AC small-signal magnitude (needed for AC analysis; default = amplitude)."""
    ac = amplitude if ac is None else ac
    return f"DC {_n(dc_level)} AC {_n(ac)} 0 Sin {_n(offset)} {_n(amplitude)} {_n(freq)} {_n(delay)} {_n(damping)} {_n(phase)}"


def pulse(v1, v2, period, width=None, delay=0, rise=1e-9, fall=1e-9, ac=None) -> str:
    """Pulse/square source switching v1 -> v2. width defaults to half the period (50 % duty)."""
    width = period / 2 - (rise + fall) / 2 if width is None else width
    return f"DC 0 AC {_n(ac if ac is not None else 1)} 0 Pulse {_n(v1)} {_n(v2)} {_n(delay)} {_n(rise)} {_n(fall)} {_n(width)} {_n(period)}"
