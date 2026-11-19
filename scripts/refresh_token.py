"""Renueva el token de Instagram (dura 60 días) y lo deja en un archivo para guardarlo como secreto.

Uso: python scripts/refresh_token.py <archivo_salida>
"""
import os
import sys
from pathlib import Path

import _boot  # noqa: F401
from autopilot import config
from autopilot.api import InstagramClient


def main(out: str) -> int:
    data = InstagramClient.refresh_token(config.env("IG_ACCESS_TOKEN"))
    token = data["access_token"]
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::add-mask::{token}")
    Path(out).write_text(token)
    days = int(data.get("expires_in", 0)) // 86400
    print(f"Token renovado: vence en {days} días.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
