# Python API

## Opening circuits

::: mc9.open
::: mc9.attach
::: mc9.close_all

## Circuit

::: mc9.api.Circuit
    options:
      members: [parts, get, set, limits, curves, show, run, op, ac, transient, dc, distortion, dynamic_dc, dynamic_ac, cursors, back, shot, export, close]

## Results

::: mc9.api.Result
::: mc9.api.Run
::: mc9.api.OP

## Measurements

::: mc9.measure
    options:
      members: [bandwidth, gain_at, rin, rout, thd, solve, set_sine, dft_harmonics, Bandwidth]

## Sources

::: mc9.sources

## Schematic builder

::: mc9.schematic.Schematic
::: mc9.schematic.Part

## Netlist and automatic placement

::: mc9.netlist.Netlist
::: mc9.autoplace.place

## Starter circuits

::: mc9.library
    options:
      members: [voltage_divider, rc_lowpass, rc_highpass, rlc_lowpass, diode_clipper, ce_amplifier, ce_feedback_amplifier, inverting_amplifier, noninverting_amplifier]

## Configuration

::: mc9.config.Config
