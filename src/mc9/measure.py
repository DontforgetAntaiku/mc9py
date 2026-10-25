"""Lab-style measurements on top of `mc9.Circuit` (each helper runs the analyses it needs in MC9).

```python
from mc9 import measure
bw = measure.bandwidth(c, "db(v(Ua)/v(Ue))")                 # G0, f_low, f_high at G0-3 dB
rin = measure.rin(c, "v(Ue)", "i(R1)", f=2224)                # |v/i| at f
rout = measure.rout(c, "v(Ua)", load="R4", f=2224)            # load-removal method
k = measure.thd(c, f0=2224, source="V1", amplitude=35e-3, out="v(Ua)")
r2 = measure.solve(c, "R2", "RESISTANCE", lambda op: op["Q1"]["VCE"], target=9.5, lo=100e3, hi=500e3)
```
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from . import results as resmod
from .api import Circuit


@dataclass
class Bandwidth:
    g0_db: float
    f0: float          # frequency of the maximum
    f_low: float | None     # None: response has no lower -3 dB edge (low-pass)
    f_high: float | None    # None: no upper edge (high-pass)

    @property
    def span(self) -> float | None:
        return None if self.f_low is None or self.f_high is None else self.f_high - self.f_low


def bandwidth(c: Circuit, expr: str, fmin: float = 1, fmax: float = 2e7, points: int = 801, drop_db: float = 3.0,
              reference: float | None = None, cursors: bool = False) -> Bandwidth:
    """-3 dB band of a gain curve [dB]. reference: take G0 at this frequency instead of the maximum."""
    r = c.ac(fmin, fmax, points, [expr])
    f0, g0 = r.peak(expr) if reference is None else (reference, r.value_at(expr, reference))
    lows = [f for f in r.cross(expr, g0 - drop_db) if f < f0]
    highs = [f for f in r.cross(expr, g0 - drop_db) if f > f0]
    if not lows and not highs:
        raise RuntimeError(f"curve never drops {drop_db} dB from its reference {g0:.4g} dB (range {fmin}..{fmax})")
    bw = Bandwidth(g0, f0, max(lows) if lows else None, min(highs) if highs else None)
    if cursors:
        edges = [f for f in (bw.f_low, bw.f_high) if f is not None]
        c.cursors(edges[0], edges[1] if len(edges) > 1 else None)
    return bw


def gain_at(c: Circuit, out: str, inp: str, f: float, points: int = 801) -> dict:
    """AC gain out/inp at one frequency: {'mag','db','phase_deg'} (interpolated from a log sweep)."""
    mag, db, ph = f"mag({out}/{inp})", f"db({out}/{inp})", f"ph({out}/{inp})"
    r = c.ac(max(f / 1000, 1e-3), f * 1000, points, [mag, db, ph])
    return {"mag": r.value_at(mag, f), "db": r.value_at(db, f), "phase_deg": r.value_at(ph, f)}


def rin(c: Circuit, node_v: str, current: str, f: float, points: int = 801) -> float:
    """Input resistance |Z| = |v(node)/i(part)| at f, from an AC run (current = e.g. 'i(R1)')."""
    expr = f"mag({node_v}/{current})"
    r = c.ac(max(f / 1000, 1e-3), f * 1000, points, [expr])
    return r.value_at(expr, f)


def rout(c: Circuit, out: str, load: str, f: float, attr: str = "RESISTANCE", open_value: str = "1T",
         points: int = 801) -> float:
    """Output resistance by load removal: Rout = (U_open / U_loaded - 1) * RL. Restores the load afterwards."""
    expr = f"mag({out})"
    rl_txt = c.get(load, attr)
    rl = resmod.parse_value(rl_txt) if isinstance(rl_txt, str) else float(rl_txt)
    lo, hi = max(f / 1000, 1e-3), f * 1000
    loaded = c.ac(lo, hi, points, [expr]).value_at(expr, f)
    c.set(load, attr, open_value)
    try:
        open_ = c.ac(lo, hi, points, [expr]).value_at(expr, f)
    finally:
        c.set(load, attr, rl_txt)
    return (open_ / loaded - 1) * rl


def set_sine(c: Circuit, source: str, amplitude=None, freq=None, attr: str = "VALUE") -> str:
    """Edit the 'Sin offset amp freq ...' part of a source's VALUE text. Returns the old text."""
    old = c.get(source, attr)
    tok = old.split()
    try:
        i = next(k for k, t in enumerate(tok) if t.lower() == "sin")
    except StopIteration:
        raise ValueError(f"{source}.{attr} = {old!r} has no 'Sin' definition") from None
    if amplitude is not None:
        tok[i + 2] = amplitude if isinstance(amplitude, str) else repr(float(amplitude))
    if freq is not None:
        tok[i + 3] = freq if isinstance(freq, str) else repr(float(freq))
    c.set(source, attr, " ".join(tok))
    return old


def dft_harmonics(t: list[float], y: list[float], f0: float, n_harm: int = 10) -> dict[int, float]:
    """Amplitudes of harmonics 1..n of f0 from uniformly sampled y over a whole number of periods."""
    n = len(y)
    out = {}
    for k in range(1, n_harm + 1):
        w = 2 * math.pi * k * f0
        re = sum(v * math.cos(w * tt) for tt, v in zip(t, y)) * 2 / n
        im = sum(v * math.sin(w * tt) for tt, v in zip(t, y)) * 2 / n
        out[k] = math.hypot(re, im)
    return out


def thd(c: Circuit, f0: float, source: str, amplitude, out: str, periods: int = 10, settle_periods: int = 80,
        samples_per_period: int = 128, n_harm: int = 10) -> dict:
    """Harmonic distortion of node/expression `out` for a sine `source` of given amplitude (steady state).
    Runs a transient, DFTs whole periods. Returns {'h': {n: amplitude}, 'k_pct': {n: % of fundamental}, 'thd_pct'}.
    Accuracy is limited by MC9's 6-digit numeric output (fine for THD down to ~0.01 %)."""
    T = 1.0 / f0
    old = set_sine(c, source, amplitude=amplitude, freq=f0)
    try:
        n = periods * samples_per_period
        t0 = settle_periods * T
        r = c.transient(t0 + periods * T, t0, points=n + 1, curves=[out], max_step=T / 400)
    finally:
        c.set(source, "VALUE", old)
    y = r[out][:-1]
    t = [t0 + i * T / samples_per_period for i in range(len(y))]   # exact grid (table x values are rounded)
    h = dft_harmonics(t, y, f0, n_harm)
    k = {i: 100 * h[i] / h[1] for i in h}
    return {"h": h, "k_pct": k, "thd_pct": math.sqrt(sum(v * v for i, v in k.items() if i > 1)), "result": r}


def solve(c: Circuit, part: str, attr: str, f: Callable, target: float, lo: float, hi: float,
          tol: float = 1e-3, max_iter: int = 14, op: bool = True) -> float:
    """Find the value of `part.attr` in [lo, hi] for which f(measurement) == target (bisection, monotonic f).
    f receives the OP (operating point); each iteration costs one MC9 start (~25 s)."""
    flo = f(_eval(c, part, attr, lo)) - target
    fhi = f(_eval(c, part, attr, hi)) - target
    if flo * fhi > 0:
        raise ValueError(f"target {target} is not bracketed: f(lo)={flo + target:.4g}, f(hi)={fhi + target:.4g}")
    for _ in range(max_iter):
        mid = math.sqrt(lo * hi) if lo > 0 and hi / lo > 10 else (lo + hi) / 2
        fm = f(_eval(c, part, attr, mid)) - target
        if abs(fm) <= tol * max(abs(target), 1e-12):
            lo = hi = mid
            break
        if fm * flo > 0:
            lo, flo = mid, fm
        else:
            hi = mid
    value = (lo + hi) / 2
    c.set(part, attr, value)
    return value


def _eval(c: Circuit, part: str, attr: str, value: float):
    c.set(part, attr, value)
    return c.op()
