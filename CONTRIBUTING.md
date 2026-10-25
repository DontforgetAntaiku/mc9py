# Contributing

Thanks for helping! The most valuable contributions are **reports and calibrations for other MC9 editions and Windows setups**,
new measurement helpers, more catalog parts and circuits that the auto-placer handles badly.

## Development setup

```bash
git clone https://github.com/DontforgetAntaiku/mc9py && cd mc9py
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev,docs]"
python -m pytest -q            # offline tests, no MC9 needed (this is what CI runs)
ruff check src tests
mkdocs serve                   # live documentation preview
```

Tests that run a real MC9 are opt-in: `MC9_INTEGRATION=1 python -m pytest tests/test_integration.py` (needs the sandbox on Linux, or MC9 on Windows).

## Ground rules

- **Never commit** MC9 binaries, installers, licence keys, decompiled code, other people's circuits or lab reports. Use circuits you built
  from code (`Schematic` / `Netlist`) for tests and examples.
- Keep platform-specific code inside `mc9/backends/`. Everything else must run (and be tested) on any OS without MC9.
- A change that affects what MC9 *does* needs a check against a real MC9; say how you verified it in the PR.
- New behaviour comes with a test; user-visible behaviour with a documentation update and a line in `CHANGELOG.md`.
- Keep screenshots native: do not re-render plots with matplotlib - the library's promise is that every picture is MC9's own.

## Reporting problems

Run `mc9 doctor`, include its output, your OS/Wine/Windows version, the MC9 edition and UI language, a minimal script, and the
`*_FAILED.png` screenshot if the library saved one.

## For maintainers: publishing

1. `python tools/set_owner.py YOUR_GITHUB_NAME [repo]` replaces the `DontforgetAntaiku` placeholders (README, docs, `pyproject.toml`, `mkdocs.yml`).
2. Push to GitHub. In *Settings -> Pages* choose **GitHub Actions** as the source; `docs.yml` builds and deploys the site on every push to `main`.
3. PyPI: create the project on pypi.org and add a *trusted publisher* for this repository and the `publish.yml` workflow (environment `pypi`);
   publishing a GitHub release then uploads the package - no token needed.
4. Bump `version` in `pyproject.toml` and `mc9/__init__.py`, add a `CHANGELOG.md` entry, tag, release.
