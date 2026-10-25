# Configuration

Settings live in `mc9.config` (set them before opening circuits) and in environment variables.

```python
import mc9
mc9.config.maximize_plots = True
mc9.config.run_timeout = 300          # slow machine / long transients
```

| Setting | Default | Meaning |
|---|---|---|
| `backend` | `"auto"` | `"auto"` picks `"windows"` on Windows and `"wine"` elsewhere; force one with `"wine"` / `"windows"` |
| `home` | see below | work directory (circuits, numeric output, screenshots; on Linux also the sandbox snapshot) |
| `mc9_exe` | `None` | path to `mc9.exe`: a Windows path inside the Wine prefix, or a native path on Windows |
| `screen` | `"2000x1100"` | virtual screen of the Linux backend (MC9's window is 1900x980, keep it at least that big) |
| `start_timeout` | `120` | seconds to wait for MC9 to start |
| `run_timeout` | `120` | seconds to wait for an analysis to finish (per call: `timeout=` argument) |
| `maximize_plots` | `True` | open analysis windows maximized so tall plot stacks are not cut off |
| `dialog_wait` | `1.0` | pause after opening MC9 dialogs; raise it on a slow machine |

## Environment variables

| Variable | Meaning |
|---|---|
| `MC9_HOME` | work directory (same as `config.home`) |
| `MC9_EXE` | `mc9.exe` location (same as `config.mc9_exe`) |
| `MC9_INTEGRATION=1` | enables the tests that run a real MC9 (`pytest tests/test_integration.py`) |

## Work directory

Resolved in this order: `config.home` -> `$MC9_HOME` -> `./sandbox` when running from a source checkout ->
`~/.local/share/mc9` (Linux) or `%LOCALAPPDATA%\mc9` (Windows). `mc9.exchange_dir()` returns the `exchange` folder inside it.

## Files written there

| File | Content |
|---|---|
| `<name>.cir` | the circuit (edits are written here before each run) |
| `<name>.TNO` `.ANO` `.DNO` `.WNO` | MC9's numeric output of the last transient / AC / DC / distortion run |
| `<name>.layout.json` | crop and zoom hints written by the schematic builder |
| `<file>.png` | screenshots you requested |
| `<name>_<analysis>_FAILED.png` | what MC9 showed when a run produced nothing |
