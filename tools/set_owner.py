"""Replace the OWNER placeholder with your GitHub user/org in README, docs, mkdocs.yml and pyproject.toml.

python tools/set_owner.py YOUR_GITHUB_NAME [repo_name]      # default repo name: mc9py
"""

import sys
from pathlib import Path

owner = sys.argv[1]
repo = sys.argv[2] if len(sys.argv) > 2 else "mc9py"
root = Path(__file__).resolve().parents[1]
files = [
    root / "README.md",
    root / "mkdocs.yml",
    root / "pyproject.toml",
    root / "CONTRIBUTING.md",
    *(root / "docs").rglob("*.md"),
    *(root / ".github").rglob("*.md"),
]
for f in files:
    t = f.read_text()
    n = t.replace("OWNER/mc9py", f"{owner}/{repo}").replace("OWNER.github.io/mc9py", f"{owner}.github.io/{repo}")
    n = n.replace("OWNER", owner)
    if n != t:
        f.write_text(n)
        print("updated", f.relative_to(root))
