"""permite ejecutar worky con ``python -m worky``."""

from __future__ import annotations

import sys

from worky.cli import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
