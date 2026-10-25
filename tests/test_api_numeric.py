import math

import pytest

from mc9 import measure
from mc9.api import Run


def ac_run():
    xs = [10 ** (i / 50) for i in range(0, 351)]  # 1 Hz .. 10 MHz, log
    rows = []
    for f in xs:  # single-pole low-pass with fc = 1 kHz
        g = -10 * math.log10(1 + (f / 1000) ** 2)
        rows.append([f, g])
    return Run("ac", ["F", "db"], ["(Hz)"], rows)


def test_cross_and_value_at_use_log_interpolation():
    r = ac_run()
    assert r.cross("db", -3.0103)[0] == pytest.approx(1000, rel=2e-3)
    assert r.value_at("db", 1000) == pytest.approx(-3.0103, abs=2e-3)
    assert r.peak("db")[0] == pytest.approx(1.0, rel=1e-6)


def test_edges_and_stats():
    t = Run("transient", ["T", "y"], [], [[i * 1e-3, math.sin(2 * math.pi * i / 100)] for i in range(201)])
    assert t.amplitude("y") == pytest.approx(1, abs=1e-3) and t.mean("y", 0, 0.1) == pytest.approx(0, abs=0.02)
    assert len(t.cross("y", 0, "rising")) == 2


def test_dft_harmonics_exact():
    f0, n = 1000.0, 256
    t = [i / (f0 * n) * 1 for i in range(n)]
    y = [1.0 * math.sin(2 * math.pi * f0 * x) + 0.1 * math.sin(2 * math.pi * 2 * f0 * x + 0.3) for x in t]
    h = measure.dft_harmonics(t, y, f0, 5)
    assert h[1] == pytest.approx(1.0, abs=1e-9) and h[2] == pytest.approx(0.1, abs=1e-9) and h[3] < 1e-9


def test_set_sine_edits_only_sin_part():
    class C:
        v = "DC 0 AC 3.5m 0 Sin 0 3.5m 2.224k 0 0 0"

        def get(self, p, a):
            return self.v

        def set(self, p, a, value):
            self.v = value

    c = C()
    measure.set_sine(c, "V1", amplitude=0.035, freq=1000)
    assert c.v == "DC 0 AC 3.5m 0 Sin 0 0.035 1000.0 0 0 0"
