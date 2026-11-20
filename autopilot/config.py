"""Rutas del proyecto, configuración y variables de entorno."""
from __future__ import annotations

import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(os.environ.get("AUTOPILOT_ROOT", Path(__file__).resolve().parent.parent))
CONFIG_DIR = ROOT / "config"
QUEUE_DIR = ROOT / "queue"
PUBLISHED_DIR = ROOT / "published"
MEDIA_DIR = ROOT / "media"
ASSETS_DIR = ROOT / "assets"
REPORTS_DIR = ROOT / "reports"
STATE_DIR = Path(os.environ.get("STATE_DIR", ROOT / ".state"))


def load_settings() -> dict:
    with open(CONFIG_DIR / "settings.json", encoding="utf-8") as fh:
        return json.load(fh)


def load_persona(with_promos: bool = True) -> str:
    text = (CONFIG_DIR / "persona.md").read_text(encoding="utf-8")
    if with_promos:
        from . import promos  # import tardío: promos usa config
        text = f"{text.rstrip()}\n\n{promos.as_markdown()}\n"
    return text


def timezone() -> ZoneInfo:
    return ZoneInfo(load_settings().get("timezone", "UTC"))


def env(name: str, required: bool = True, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise SystemExit(
            f"Falta la variable {name}. Agrégala en GitHub → Settings → "
            f"Secrets and variables → Actions (ver SETUP.md)."
        )
    return value


def dry_run() -> bool:
    return os.environ.get("DRY_RUN", "").lower() in {"1", "true", "yes", "si", "sí"}
