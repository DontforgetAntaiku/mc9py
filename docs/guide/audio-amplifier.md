# Audio power amplifier (coursework)

The classic electronics coursework - *design a class-AB, inverting, bipolar, dual-supply power amplifier from a table row and prove
it by simulation in Micro-Cap* - needs the same dozen measurements every time. `mc9.audio` does them and keeps MC9's own plots for the
explanatory note.

```python
import mc9
from mc9 import audio

# P_out [W], R_load [ohm], R_in [ohm], f_low [Hz], f_high [Hz], THD [%]; nominal input amplitude 1 V
specs = audio.Specs(p_out=24, r_load=6, r_in=60e3, f_low=25, f_high=18e3, thd=0.3)
specs.summary()          # Uout_m = 17 V, Iout_m = 2.8 A, gain = 17, Vcc = 23 V, class-B efficiency 58 %, worst-case dissipation 17.9 W ...
```

## 1. The numbers you calculate by hand

| Quantity | Formula (in `Specs`) |
|---|---|
| output amplitude | `v_out = sqrt(2 P R_L)` |
| output current amplitude | `i_out = v_out / R_L` |
| gain | `v_out / u_in` (inverting: R_F = gain x R_in) |
| supply voltage | `vcc` ~ `v_out` + saturation + emitter-resistor and driver drops |
| utilisation of the supply | `xi = v_out / Vcc` |
| ideal class-B supply power / efficiency | `2 Vcc v_out / (pi R_L)`, `P_out / P_supply` |
| worst-case dissipation of the output pair | `2 Vcc^2 / (pi^2 R_L)` at `v_out = 2 Vcc / pi` |

## 2. A starter circuit

`audio.schematic(specs)` draws (and `audio.power_amplifier(specs)` describes as a `Netlist`) an inverting stage: R_in, an op-amp
(default LF411) with R_F || C_F, and a complementary Darlington output stage (BD139/BD140 drivers, MJ15003/MJ15004 power
transistors, 0.33 ohm emitter resistors) **inside the feedback loop**, biased by a diode string, with a Zobel network. The drawing
is MC9's own file; the parts and values are yours to change - it is a starting point, not the answer to your variant.

```python
c = audio.schematic(specs).build("amp", labels="dc")
bench = audio.Bench(c, specs)           # part names can be given if your circuit uses other ones
bench.tune_quiescent(0.05)              # set the bias so each output transistor idles at 50 mA
```

## 3. The measurements

| Method | What it gives |
|---|---|
| `bench.ac_response(temps=[0, 25, 70])` | A0, the -3 dB edges f_low / f_high (against the maximum), phase there, peaking, phase-margin estimate; MC9's plot with cursors on the edges |
| `bench.sine_at(f)` | steady state at f_low, f_0, f_high: output amplitude, power, mean supply current, efficiency (per temperature) |
| `bench.clipping()` | output levels at double input amplitude, supply utilisation |
| `bench.square_wave(f)` | rise/fall time (10-90 %), slew rates, overshoot |
| `bench.distortion(1e3)`, `(1e4)` | THD and harmonics at nominal power; MC9's harmonic window |
| `bench.max_power(thd_limit=10)` | largest power at 10 % THD (bisection) |
| `bench.power_bandwidth(slew)` | full-power frequency `SR / (2 pi V_pk)` |
| `bench.output_resistance()` | R_out by load removal |
| `bench.quiescent()` | output offset, idle currents |
| `bench.dissipation()` | mean power in the output pair at 0.3...0.8 Vcc: the worst case |

`audio.report(bench)` runs all of it; `audio.format_report(results, specs)` prints the table "required / theory / simulated" for the
note. Every plot is a screenshot of MC9 (`<name>_ac_gain_phase.png`, `<name>_sine_fl.png`, `<name>_square_f0.png`,
`<name>_harmonics_1000Hz.png` ...) in the exchange folder.

!!! note "Phase margin"
    The loop gain of a closed-loop circuit is not directly visible in MC9; the module estimates the margin from the closed-loop
    peaking (`phase_margin_from_peaking`). For the exact value break the loop with a source in series with R_F and run an AC analysis.
