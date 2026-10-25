# The Windows backend

`mc9/backends/windows.py` drives a native MC9 with the Win32 API through `ctypes` (plus Pillow for the screenshot). No third-party
automation library is needed.

| Need | Win32 mechanism |
|---|---|
| start MC9 on a circuit | `subprocess.Popen([mc9.exe, circuit.cir])`; wait for a visible top-level window of that process |
| make coordinates valid | `SetWindowPos` to (0,0), 1900x980 |
| open analysis / run / leave | `SendInput` of MC9's accelerators: `Alt+1`.., `F2`, `F3` (language independent) |
| find dialogs | `EnumWindows` filtered by process id and class `#32770`; controls via `EnumChildWindows` |
| fill / press | `WM_SETTEXT` on the edit control, `BM_CLICK` on buttons via `SendMessageTimeout` (a plain `SendMessage` hangs when the button opens a modal dialog) |
| toolbar icons, blank canvas | mouse clicks with `SendInput` (icon positions are identical in all languages) |
| screenshot | `PIL.ImageGrab.grab(bbox=window rect)` |
| shut down | `Popen.kill()` (nothing is ever saved, so no "save changes?" prompt) |

## Testing without a Windows machine

CI cannot run MC9, but the driver can be exercised on Linux: install a Windows build of Python into the sandbox prefix and run the
whole library as a Windows process under Wine - it then starts MC9 as a *native Windows process* and uses the same Win32 calls:

```bash
tools/install_winpy.sh            # Windows Python + Pillow into the sandbox prefix
tools/test_windows_backend.sh     # runs tools/win_smoke.py: op, AC, cursors, screenshots, dynamic DC
```

## Known limits

- Real-Windows coverage is still thin. Reports with `mc9 doctor` output and a screenshot are very welcome.
- Needs 100 % display scaling and a screen of at least 1900x980; do not touch mouse or keyboard while a script runs.
- MC9 shows first-run dialogs (registration, tips) on a fresh install - dismiss them once by hand.
