#!/usr/bin/env bash
# Start MC9 under the Wine sandbox with mc9hook.dll loaded, then run a Python script that talks to it.
# usage: tools/test_native_hook.sh <script.py>      (the script uses mc9.native.Hook)
set -euo pipefail
R="$(cd "$(dirname "$0")/.." && pwd)"; EX="$R/sandbox/exchange"
make -C "$R/native" -s
cp "$R/native/mc9hook.dll" "$R/native/mc9launch.exe" "$EX/"
[ -f "$R/native/signatures.txt" ] && cp "$R/native/signatures.txt" "$EX/"
rm -f "$EX"/hook.req* "$EX"/hook.resp* "$EX"/launch.log
cd "$R"
setsid uv run python - > "$EX/sandbox_run.log" 2>&1 <<'PY' &
from mc9.backends import linux_wine
import subprocess, sys
cmd = linux_wine.bwrap_command(["bash", "-c", r'''
Xvfb :99 -screen 0 2000x1100x24 </dev/null >/dev/null 2>&1 &
sleep 2; export DISPLAY=:99
wine 'C:\exchange\mc9launch.exe' 'C:\exchange\mc9hook.dll' 'C:\Program Files (x86)\mc9g\mc9.exe' 'C:\exchange\auto_ce_amp.cir' > /home/sbx/exchange/launch.log 2>&1
sleep 600
'''])
sys.exit(subprocess.run(cmd, timeout=900).returncode)
PY
LEAD=$!
trap 'kill -- -$LEAD 2>/dev/null || true' EXIT
for i in $(seq 1 60); do grep -q "loaded=" "$EX/launch.log" 2>/dev/null && break; sleep 1; done
cat "$EX/launch.log" 2>/dev/null | grep -E "loaded|failed" || true
uv run python "$R/tools/${1:?script}"
