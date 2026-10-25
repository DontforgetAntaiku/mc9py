#!/usr/bin/env bash
# Developer tool: put a Windows Python (+Pillow) into the sandbox prefix so the *Windows backend* can be tested under Wine.
#   tools/install_winpy.sh            (downloads into tools/winpy-dl/ first run; afterwards works offline)
set -euo pipefail
R="$(cd "$(dirname "$0")/.." && pwd)"; DL="$R/tools/winpy-dl"; mkdir -p "$DL"
[ -f "$DL/py.zip" ] || curl -sL -o "$DL/py.zip" https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip
[ -d "$DL/wheels" ] || (cd "$DL" && uv run --with pip pip download pillow --platform win_amd64 --python-version 3.12 --only-binary=:all: --no-deps -d wheels)
for P in "$R/sandbox/prefix-pristine" "$R/sandbox/prefix-work"; do
  [ -d "$P/drive_c" ] || continue
  T="$P/drive_c/winpy"; rm -rf "$T"; mkdir -p "$T/Lib/site-packages"
  python3 -I -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$DL/py.zip" "$T"
  for w in "$DL"/wheels/*.whl; do python3 -I -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$w" "$T/Lib/site-packages"; done
  printf 'python312.zip\n.\nLib\\site-packages\nC:\\exchange\\winsrc\nimport site\n' > "$T/python312._pth"
  echo "installed Windows Python into $T"
done
