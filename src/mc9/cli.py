"""Command line: `mc9 setup|doctor|reset|mcp|version`."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__, workspace
from .config import config


def _ok(flag: bool, text: str, hint: str = "") -> bool:
    print(f"  [{'ok' if flag else 'FAIL'}] {text}" + (f"  -> {hint}" if hint and not flag else ""))
    return flag


def _find_exe(prefix: Path) -> str | None:
    """mc9.exe inside a Wine prefix, as a Windows path."""
    drive_c = prefix / "drive_c"
    for pat in ("Program Files (x86)/*/mc9.exe", "Program Files/*/mc9.exe", "*/mc9.exe", "Program Files (x86)/*/*/mc9.exe"):
        for f in sorted(drive_c.glob(pat)):
            return "C:\\" + str(f.relative_to(drive_c)).replace("/", "\\")
    return None


def cmd_setup(a) -> int:
    src = Path(a.prefix).expanduser().resolve()
    if not (src / "drive_c").is_dir():
        print(f"{src} is not a Wine prefix (no drive_c). Install MC9 into a prefix first: WINEPREFIX=~/.wine wine setup.exe")
        return 1
    if a.home:
        config.home = a.home
    home = workspace.home()
    dst = home / "prefix-pristine"
    if dst.exists():
        print(f"{dst} already exists; delete it to redo setup")
        return 1
    exe = _find_exe(src)
    home.mkdir(parents=True, exist_ok=True)
    (home / "exchange").mkdir(exist_ok=True)
    print(f"copying the Wine prefix ({src}) to {dst} ...")
    subprocess.run(["cp", "-a", "--reflink=auto", str(src), str(dst)], check=True)
    users = dst / "drive_c" / "users"
    for link in list(users.glob("*/*")):                    # links to your real home folders would leak files
        if link.is_symlink():
            link.unlink()
            link.mkdir()
    z = dst / "dosdevices" / "z:"
    if z.is_symlink() or z.exists():
        z.unlink()
    (dst / "drive_c" / "exchange").mkdir(exist_ok=True)
    if exe:
        workspace.save_settings(mc9_exe=exe)
    print(f"done. data dir: {home}\n  mc9.exe: {exe or 'NOT FOUND - set mc9.config.mc9_exe or $MC9_EXE'}\n  next: mc9 doctor")
    return 0


def cmd_reset(_a) -> int:
    from .backends import linux_wine
    linux_wine.reset()
    print("working Wine prefix discarded; it is recreated from the pristine snapshot on next use")
    return 0


def cmd_doctor(_a) -> int:
    print(f"mc9 {__version__}  python {sys.version.split()[0]}  platform {sys.platform}")
    good = True
    try:
        import PIL  # noqa: F401
        good &= _ok(True, "Pillow")
    except ImportError:
        good &= _ok(False, "Pillow", "pip install pillow")
    if sys.platform == "win32":
        from .backends.windows import find_mc9
        try:
            exe = find_mc9()
            good &= _ok(Path(exe).exists(), f"mc9.exe: {exe}", "set mc9.config.mc9_exe")
        except FileNotFoundError as e:
            good &= _ok(False, "mc9.exe", str(e))
        print("  note: use 100 % display scaling; keep the MC9 window visible while a script runs")
        return 0 if good else 1
    for tool, hint in (("wine", "install wine"), ("bwrap", "install bubblewrap"), ("Xvfb", "install xorg-server-xvfb / xvfb"),
                       ("xdotool", "install xdotool"), ("import", "install imagemagick")):
        good &= _ok(shutil.which(tool) is not None, f"{tool} in PATH", hint)
    loc = subprocess.run(["locale", "-a"], capture_output=True, text=True).stdout.lower()
    _ok("ru_ru.utf8" in loc or "ru_ru.utf-8" in loc, "locale ru_RU.UTF-8 (needed only for the Russian MC9 edition)",
        "generate it, or edit LANG in backends/linux_wine.py for another edition")
    home = workspace.home()
    good &= _ok((home / "prefix-pristine").is_dir(), f"sandbox snapshot {home / 'prefix-pristine'}", "run: mc9 setup /path/to/wine-prefix")
    import os
    exe = config.mc9_exe or os.environ.get("MC9_EXE") or workspace.settings().get("mc9_exe")
    if not exe and (home / "prefix-pristine").is_dir():
        exe = _find_exe(home / "prefix-pristine")
    good &= _ok(bool(exe), f"mc9.exe in the prefix: {exe}", "run mc9 setup, or set $MC9_EXE")
    return 0 if good else 1


def cmd_mcp(_a) -> int:
    try:
        from .server import main as serve
    except ImportError as e:
        print(f"the MCP server needs the 'mcp' extra: pip install 'mc9py[mcp]'  ({e})")
        return 1
    serve()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mc9", description="Scripting layer for Micro-Cap 9")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup", help="create the sandbox snapshot from a Wine prefix where MC9 is installed (Linux)")
    s.add_argument("prefix")
    s.add_argument("--home", help="data directory (default: ~/.local/share/mc9)")
    s.set_defaults(fn=cmd_setup)
    sub.add_parser("reset", help="discard the working Wine prefix (Linux)").set_defaults(fn=cmd_reset)
    sub.add_parser("doctor", help="check that everything needed is installed").set_defaults(fn=cmd_doctor)
    sub.add_parser("mcp", help="run the MCP server (stdio)").set_defaults(fn=cmd_mcp)
    sub.add_parser("version").set_defaults(fn=lambda _a: print(__version__) or 0)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
