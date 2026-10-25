# Architecture

```
            your script / AI assistant
                      |
   mc9.Circuit  mc9.Schematic  mc9.Netlist  mc9.measure      <- pure Python, platform independent
   (api.py)     (schematic.py) (autoplace.py) (measure.py)
        |                              |
   cir.py (circuit file editor)   results.py (numeric output parser)
        |
   ui.py  - flows: run an analysis, cursors, screenshots, error capture
        |
   backends.Driver  (backends/base.py)
     |-- linux_wine.py : bubblewrap sandbox + Wine + Xvfb + xdotool + ImageMagick
     `-- windows.py    : Win32 API through ctypes (SendInput, window/dialog messages, GDI capture)
        |
   MC9 (mc9.exe)  ->  reads/writes files in the work directory
```

## Why GUI automation

MC9 is a classic MFC application with no scripting interface, no batch mode and no COM automation (the command line only
opens a file or prints). The only supported ways to use it are its windows. `mc9py` therefore:

1. **edits the circuit file** (an INI-like text format) so that all settings - analysis limits, curves, dynamic-analysis
   options, window state, numeric output - are configured *in the file*, not by typing into dialogs;
2. starts MC9 on that file and presses the few buttons that remain (open analysis, Run, OK, cursor dialog);
3. reads the **numeric output files** MC9 writes for the numbers, and takes **screenshots** of its window for the pictures.

Doing as much as possible in the file keeps the GUI part tiny and robust.

## The Driver interface

`Driver` has seven methods: `open_analysis`, `press_run`, `confirm_dynamic`, `set_cursors`, `exit_analysis`, `prepare_capture`,
`grab` (+ `close`). Everything above it (`ui.MC9`, `Circuit`) is shared between operating systems. Adding a backend (for example
macOS with CrossOver, or a remote VM) means implementing those methods.

## Sandbox (Linux)

`bwrap --unshare-all` (no network, no IPC sharing), an empty `$HOME`, read-only `/usr` and `/etc`, and exactly two writable
directories: a private copy of the Wine prefix and the exchange folder. Your own Wine prefix and files are never mounted.
The pristine snapshot has its links to your real home folders and the `Z:` drive (which maps `/`) removed.

## Numbers vs. pictures

Numbers come from MC9's numeric output with `OUTPUT` enabled on each curve, which is why they match what MC9 shows.
Pictures are screenshots, cropped by region constants (`layout.py`) or, for schematics, by the geometry the builder computed.
