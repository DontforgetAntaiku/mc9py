# Install on Linux

On Linux, MC9 runs **inside a sandbox**: Wine + a virtual display (Xvfb) + bubblewrap. Your files and your normal Wine
prefix are never touched, there is no network access, and nothing pops up on your screen.

## 1. System packages

| Tool | Why | Arch | Debian / Ubuntu | Fedora |
|---|---|---|---|---|
| wine | runs MC9 | `wine` | `wine` | `wine` |
| bubblewrap | the sandbox | `bubblewrap` | `bubblewrap` | `bubblewrap` |
| Xvfb | virtual display | `xorg-server-xvfb` | `xvfb` | `xorg-x11-server-Xvfb` |
| xdotool | mouse/keyboard | `xdotool` | `xdotool` | `xdotool` |
| ImageMagick | screenshots (`import`) | `imagemagick` | `imagemagick` | `ImageMagick` |

## 2. Python package

mc9py is not on PyPI yet, so `pip install mc9py` does not work; install it from GitHub into a virtual environment
(a private folder for Python packages, so nothing is installed system-wide):

```bash
python3 -m venv ~/mc9-env
source ~/mc9-env/bin/activate            # repeat this in every new terminal
pip install "git+https://github.com/DontforgetAntaiku/mc9py.git"
mc9 version
```

Alternatives: `pipx install "git+https://github.com/DontforgetAntaiku/mc9py.git"` puts the `mc9` command on your `PATH`
without activating anything. For the MCP server for AI assistants add the extra:
`pip install "mc9py[mcp] @ git+https://github.com/DontforgetAntaiku/mc9py.git"` (see the [MCP guide](../guide/mcp.md)).

## 3. A Wine prefix with MC9

Install MC9 once into any Wine prefix (the default `~/.wine` is fine):

```bash
WINEPREFIX=~/.wine wine /path/to/mc9-setup.exe
```

## 4. Create the sandbox snapshot

```bash
mc9 setup ~/.wine       # copies the prefix into ~/.local/share/mc9/prefix-pristine and removes links to your home folders
mc9 doctor              # checks that everything is in place
```

`mc9 setup` also records where `mc9.exe` is inside the prefix. The working copy of the prefix (`prefix-work`) is created from the
snapshot on first use; `mc9 reset` throws it away.

!!! note "UI language"
    The menu/dialog coordinates in `mc9.layout` were calibrated on the Russian *GUAP Edition* of MC9 9.0.3 at a
    1900x980 window. The Wine locale is set to `ru_RU.UTF-8` for that edition. Other editions need a one-time calibration -
    see [Supporting other MC9 editions](../internals/calibration.md).

## Where things live

`~/.local/share/mc9/` (override with `MC9_HOME` or `mc9.config.home`):

```
prefix-pristine/   snapshot of the Wine prefix (read-only use)
prefix-work/       private working copy MC9 runs in
exchange/          circuits, numeric output, screenshots  (C:\exchange inside Wine)
settings.json      location of mc9.exe, written by `mc9 setup`
```
