#!/usr/bin/env bash
# Create the sandbox snapshot from a Wine prefix in which Micro-Cap 9 is installed.
#   tools/make_sandbox.sh /path/to/.wine
# The copy is made safe: links from the prefix to your real home folders (Desktop, Documents, ...) and the
# Z: drive (= /) are removed, so MC9 inside the bwrap sandbox cannot reach your files even without bwrap.
set -euo pipefail
SRC="${1:?usage: make_sandbox.sh /path/to/wine-prefix}"
D="$(cd "$(dirname "$0")/.." && pwd)/sandbox"
[ -d "$SRC/drive_c" ] || { echo "not a Wine prefix: $SRC" >&2; exit 1; }
[ -e "$D/prefix-pristine" ] && { echo "$D/prefix-pristine already exists; delete it first" >&2; exit 1; }
mkdir -p "$D/exchange"
cp -a --reflink=auto "$SRC" "$D/prefix-pristine"
find "$D/prefix-pristine/drive_c/users" -maxdepth 2 -type l | while read -r l; do rm "$l"; mkdir "$l"; done
rm -f "$D/prefix-pristine/dosdevices/z:"
mkdir -p "$D/prefix-pristine/drive_c/exchange"
if find "$D/prefix-pristine" -type l -lname "$HOME*" | grep -q .; then echo "WARNING: links to \$HOME remain" >&2; fi
echo "sandbox snapshot ready: $D/prefix-pristine (working copy is created on first use; reset with sandbox/reset.sh)"
