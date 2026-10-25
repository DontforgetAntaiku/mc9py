# Install on Windows

On Windows the library drives your **native** MC9 directly. There is no sandbox, so work on copies of your circuits
(the library always does: `mc9.open()` copies the file into its work folder).

!!! warning "Status"
    The Windows backend is implemented with the Win32 API only (ctypes + Pillow) and is tested by running Windows Python
    under Wine against MC9, which exercises the same API calls. It has not yet had broad testing on real Windows machines -
    please report what you see ([issue template](https://github.com/DontforgetAntaiku/mc9py/issues/new/choose)).

## Steps

1. Install Python 3.10+ and MC9.
2. Install mc9py into a virtual environment (PowerShell):

    ```powershell
    py -m venv $HOME\mc9-env
    & $HOME\mc9-env\Scripts\Activate.ps1          # repeat this in every new PowerShell window
    pip install mc9py
    ```
3. Set your display scaling to **100 %** (Settings -> Display) - the screenshot regions assume it.
4. `mc9 doctor` - finds `mc9.exe` (usual install folders and `PATH`). If it is somewhere else:

```python
import mc9
mc9.config.mc9_exe = r"D:\Tools\MC9\mc9.exe"
```

## What to expect

- MC9 opens as a normal window, is moved to the top-left corner and resized to 1900x980. **Do not use the mouse or keyboard
  while a script runs** - the library sends real input events.
- Screens smaller than 1900x980 cannot show the whole window; use a larger monitor or a virtual display.
- The Windows driver is language independent: it opens analyses with MC9's keyboard accelerators (`Alt+1` transient,
  `Alt+2` AC, ...), runs with `F2`, and finds dialog buttons by class and order instead of by pixel position.

## Work folder

`%LOCALAPPDATA%\mc9\exchange` holds circuits, numeric output and screenshots (override with the `MC9_HOME` environment variable).
