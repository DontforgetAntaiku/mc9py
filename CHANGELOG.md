# Changelog

## Unreleased
- Experimental native hook (`native/`, `config.native`): `mc9hook.dll` finds MC9's functions at run time (byte patterns, string anchors,
  MFC message maps) and lets the drivers post commands directly instead of clicking menus.

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
