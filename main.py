"""Entry point for HSR Auto Skip."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path when run as script
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    from app.config import bootstrap_runtime_files
    from app.dpi import set_dpi_aware

    # Seed config/assets next to the .exe on first run
    bootstrap_runtime_files()

    # Must run before any window / screenshot calls
    set_dpi_aware()

    from app.ui import run

    run()


if __name__ == "__main__":
    main()
