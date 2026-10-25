"""``python -m mc9 ...`` is the same as the ``mc9`` command."""

from mc9.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
