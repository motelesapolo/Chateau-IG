"""Hace importable el paquete `autopilot` al correr `python scripts/<algo>.py`."""
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(levelname)s %(message)s")


def step_summary(markdown: str) -> None:
    """Escribe en el resumen visible de GitHub Actions (y en pantalla)."""
    print(markdown)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(markdown + "\n")
