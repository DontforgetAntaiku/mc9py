"""Where MC9's working files live (shared between this library and the MC9 process)."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from .config import config

NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def home() -> Path:
    """Data directory: config.home > $MC9_HOME > ./sandbox of a source checkout > per-user data dir."""
    if config.home:
        return Path(config.home).expanduser()
    if os.environ.get("MC9_HOME"):
        return Path(os.environ["MC9_HOME"]).expanduser()
    checkout = Path(__file__).resolve().parents[2]
    if (checkout / "pyproject.toml").exists() and (checkout / "sandbox").exists():
        return checkout / "sandbox"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "mc9"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "mc9"


def exchange() -> Path:
    """Folder that holds circuits, numeric output and screenshots (C:\\exchange inside the Wine prefix)."""
    d = home() / "exchange"
    d.mkdir(parents=True, exist_ok=True)
    return d


def path(name: str) -> Path:
    """Path of circuit `name` (without .cir)."""
    if not NAME_RE.match(name) or name.lower().endswith(".cir"):
        raise ValueError("circuit name: letters/digits/_.- only, without .cir")
    return exchange() / f"{name}.cir"


def settings() -> dict:
    """User settings written by `mc9 setup` (e.g. the location of mc9.exe inside the Wine prefix)."""
    import json
    f = home() / "settings.json"
    try:
        return json.loads(f.read_text())
    except (OSError, ValueError):
        return {}


def save_settings(**kv) -> None:
    import json
    d = settings()
    d.update(kv)
    home().mkdir(parents=True, exist_ok=True)
    (home() / "settings.json").write_text(json.dumps(d, indent=2))
