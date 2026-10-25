# The native hook (experimental)

`native/` holds a small DLL, `mc9hook.dll`, that is loaded **into** MC9 so the library can reach MC9's own code instead of
clicking. It is experimental: today it finds MC9's functions by itself and answers queries; calling the analysis code directly
is the next step.

## Offset auto-search

MC9 has no exported API, so every function has to be *found*. Nothing in the DLL contains an address; each build is searched at run time:

1. **Unpacking.** The shipped `mc9.exe` is UPX-packed, and the packer's section table stays in memory, so sections are not
   trusted. The DLL waits until the code area is filled and then treats the module as the list of its committed memory regions.
2. **Byte patterns.** `tools/sigmaker.py` takes the unpacked `mc9.exe`, picks the shortest wildcarded pattern of the function's first bytes
   that is unique (absolute addresses and call/jump displacements are `??`), and writes `native/signatures.txt`.
3. **String anchors.** If the pattern no longer matches (another build), the DLL finds a text string the function uses, finds the code
   that loads it and walks back to the function start (16-byte aligned, behind `CC` padding).
4. **MFC message maps.** Command handlers are found from the `WM_COMMAND` tables (`AFX_MSGMAP_ENTRY`), by command id.

`resolve` reports how each target was found and whether it is where the build the signatures came from had it (`as-built` / `MOVED`).
Both the pattern and the anchor method find all targets in the tested MC9 9.0.3 build (`tools/native_probe.py`).

## Building and trying it

```bash
make -C native                       # needs i686-w64-mingw32-gcc (32-bit, MC9 is a 32-bit program)
tools/test_native_hook.sh native_probe.py     # Linux/Wine sandbox: start MC9 with the DLL loaded and query it
```

`mc9launch.exe <dll> <program> [args]` starts a program and loads the DLL into it. Requests and answers are small files
(`hook.req`, `hook.resp`) in the exchange folder, wrapped by `mc9.native.Hook`; the same transport works on Linux and Windows.

## Supporting another MC9 build

```bash
python tools/sigmaker.py unpacked-mc9.exe native/targets.txt > native/signatures.txt     # `upx -d` first
```

Add new functions to `native/targets.txt` (`name = "a string the function uses"` or `name = 0xADDRESS`).
`signatures.txt` contains only a few short byte patterns of MC9's code, needed for matching; it does not contain any program text.
