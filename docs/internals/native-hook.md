# The two engines

MC9 has no scripting interface, so something has to operate it. mc9py has two separate ways to do that. A session uses
exactly one of them; they never mix.

| | **native** (default) | **clicks** |
|---|---|---|
| How | `mc9hook.dll` runs inside MC9; commands are posted to its window and dialogs are filled through their controls | mouse and keyboard events at calibrated positions |
| Needs | the prebuilt DLL (shipped in the wheel) | nothing extra |
| Screen coordinates | none | yes (calibrated for one MC9 edition on Linux) |
| Keyboard focus / mouse | not used | used (keep them free) |
| Optimizer | yes | no |
| Where | `backends/native.py` | `backends/linux_wine.py`, `backends/windows.py` |

```python
mc9.config.engine = "auto"      # default: native, and only if the DLL cannot start at all, clicks (with a warning)
mc9.config.engine = "native"    # fail instead of falling back
mc9.config.engine = "clicks"
```

Both engines read the same files: the circuit is edited as a `.cir`, results come from MC9's numeric output, pictures are MC9's own
screenshots. Stepping, Monte Carlo, temperatures and curves therefore work with either engine.

## How the native engine works

1. **Start.** MC9 is started and `mc9hook.dll` is loaded into it (`mc9launch.exe`, a 32-bit injector, because MC9 is a 32-bit program).
2. **Talk.** Requests and answers are small files in the exchange folder (`hook.req`, `hook.resp`), so the same code works on Linux
   under Wine and on Windows (`mc9.native.Hook`).
3. **Commands.** MC9 numbers its menu and accelerator commands per build. The numbers of the calibrated build are built in
   (`mc9.native.KNOWN_IDS`); for another build they are learned once by pressing the accelerator (Alt+1, F2, ...) and reading the
   `WM_COMMAND` MC9 receives, then saved in `settings.json` under the fingerprint of that build. Afterwards a command is *posted*
   to MC9's window - exactly what a menu click would send.
4. **Dialogs.** The DLL lists MC9's dialogs and their controls (class, id, text, position) and can set text and click buttons
   from inside the process. The Dynamic DC/AC dialogs, the cursor ("go to X") dialog and the optimizer are driven this way.
5. **Pictures.** The screenshot of MC9's window is taken by the platform (Xvfb `import` or `ImageGrab`), then cropped. Nothing is redrawn.

## Offset auto-search

The DLL contains no addresses of MC9. Every build is searched at run time:

1. **Unpacking.** The shipped `mc9.exe` is UPX-packed and the packer's section table stays in memory, so sections are not trusted.
   The DLL waits until the code area is filled and treats the module as its committed memory regions.
2. **Byte patterns.** `tools/sigmaker.py` takes the unpacked `mc9.exe`, picks the shortest wildcarded pattern of a function's first bytes
   that is unique (absolute addresses and call/jump displacements become `??`) and writes `native/signatures.txt`.
3. **String anchors.** If the pattern no longer matches (another build), the DLL finds a text string the function uses, finds the code
   that loads it and walks back to the function start (16-byte aligned, behind `CC` padding).
4. **MFC message maps.** Command handlers are found from the `WM_COMMAND` tables (`AFX_MSGMAP_ENTRY`) by command id.

`resolve` reports how each target was found and whether it is where the build the signatures came from had it (`as-built` / `MOVED`).
Both methods find all targets in the tested MC9 9.0.3 build (`tools/native_probe.py`).

## Building, testing, supporting another build

```bash
make -C native package          # needs i686-w64-mingw32-gcc; writes src/mc9/_native/ (CI does this before building the wheel)
tools/test_native_hook.sh native_probe.py       # start MC9 with the DLL and check the auto-search
python tools/sigmaker.py unpacked-mc9.exe native/targets.txt > native/signatures.txt     # `upx -d` first
```

`signatures.txt` contains only a few short byte patterns of MC9's code, needed for matching; it does not contain any program text.
If you use another MC9 edition, command ids are learned by themselves (one key press each) but the control ids of the dialogs
(`mc9.backends.native.OPT`) belong to the calibrated build; see [Supporting other MC9 editions](calibration.md).
