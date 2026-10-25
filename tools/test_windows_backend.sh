#!/usr/bin/env bash
# Test the Windows backend on Linux: Windows Python (tools/install_winpy.sh) inside Wine drives MC9 natively.
set -euo pipefail
R="$(cd "$(dirname "$0")/.." && pwd)"; EX="$R/sandbox/exchange"
rm -rf "$EX/winsrc"; mkdir -p "$EX/winsrc"; cp -r "$R/src/mc9" "$EX/winsrc/mc9"; cp "$R/tools/${1:-win_smoke.py}" "$EX/win_test.py"
cd "$R" && uv run python - <<'PY'
from mc9.backends import linux_wine
import subprocess, sys
cmd = linux_wine.bwrap_command(["bash", "-c", r'''
Xvfb :99 -screen 0 2000x1100x24 </dev/null >/dev/null 2>&1 &
sleep 2; export DISPLAY=:99 MC9_HOME='C:\'
wine "C:\winpy\python.exe" "C:\exchange\win_test.py" > /home/sbx/exchange/win_test.log 2>&1; echo "exit=$?" >> /home/sbx/exchange/win_test.log
'''])
sys.exit(subprocess.run(cmd).returncode)
PY
