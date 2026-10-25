# Changelog

## 0.2.0 - unreleased
- Windows backend (Win32 API via ctypes), tested by running Windows Python under Wine.
- Automatic placement: `Netlist` -> placed and routed `Schematic` (backbone + branches, buses, label fallback), verified net-for-net.
- `Schematic.pin_nets()`, `audit()`, label-aware connectivity (`nets()` joins equal names and all grounds).
- One package `mc9`; `workspace` paths; `Driver` abstraction; CLI (`mc9 setup | doctor | reset | mcp`).
- MCP tools `build_netlist` and others; documentation site; CI.

## 0.1.0
- First version: Linux/Wine sandbox, circuit editing, analyses with numeric results, cursors, native screenshots, `Schematic` builder,
  measurements (bandwidth, Rin, Rout, THD, solver), MCP server.
