# Changelog

## Unreleased
- **Two engines.** `mc9.config.engine`: *native* (default; `mc9hook.dll` inside MC9 posts MC9's own commands and fills its dialogs - no mouse,
  keyboard or screen coordinates) and *clicks* (the old mouse/keyboard drivers, used only if the DLL cannot start). The prebuilt DLL is shipped in the wheel.
- **Offset auto-search** inside MC9 (byte patterns, string anchors, MFC message maps), `tools/sigmaker.py` for other builds.
- **Many runs:** `Circuit.step`, `stepping_mode`, `clear_steps` (written as MC9's `[Stepping]` sections), temperature lists, Monte Carlo
  (`tolerance`, `monte_carlo`, `model`), run parameters (`run.params`, `result.select`), the optimizer (`optimize`, native engine).
- **Any MC9 part** in `Netlist`/`Schematic`: definitions are learned from MC9 on first use (`catalog.learn`), placed by the generic placer
  (transistor-like parts on the signal path, everything else beside the circuit joined by node names), `J`, `JP`, `MP`, `Z`, `E`, `SW` helpers.
- **`mc9.audio`**: audio power-amplifier coursework (specs -> derived numbers, starter circuit, `Bench` measurements, `report`).
- `measure.statistics`, `measure.per_run`, `Circuit.histogram`.
- Curve options (`xrange`, `yrange`, `xlog`, `ylog`, grid, colour), FFT plots; six new MCP tools; `mc9 doctor` checks the DLL.

## 0.2.1 - 2026-10-25
- Python 3.14 support (CI and classifiers); `python -m mc9`; install instructions now use PyPI.
- Copyright holder set to DontforgetAntaiku; MCP setup instructions for beginners.

## 0.2.0 - 2026-10-25
- Windows backend (Win32 API via ctypes), tested by running Windows Python under Wine.
- Automatic placement: `Netlist` -> placed and routed `Schematic` (backbone + branches, buses, label fallback), verified net-for-net.
- `Schematic.pin_nets()`, `audit()`, label-aware connectivity (`nets()` joins equal names and all grounds).
- One package `mc9`; `workspace` paths; `Driver` abstraction; CLI (`mc9 setup | doctor | reset | mcp`).
- MCP tools `build_netlist` and others; documentation site; CI.

## 0.1.0
- First version: Linux/Wine sandbox, circuit editing, analyses with numeric results, cursors, native screenshots, `Schematic` builder,
  measurements (bandwidth, Rin, Rout, THD, solver), MCP server.
