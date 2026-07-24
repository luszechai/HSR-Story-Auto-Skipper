"""Entry point for HSR Auto Skip."""

from __future__ import annotations

from app.config import bootstrap_runtime_files
from app.dpi import set_dpi_aware
from app.ui import run


def main() -> None:
    # Seed config/assets next to the .exe on first run
    bootstrap_runtime_files()

    # Must run before any window / screenshot calls
    set_dpi_aware()

    run()


if __name__ == "__main__":
    main()
