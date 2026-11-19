"""Crea o actualiza los issues de revisión semanal (uno por semana) con las vistas previas.

Uso: python scripts/review_issue.py   (en GitHub Actions usa GITHUB_TOKEN y GITHUB_REPOSITORY)
"""
import sys
from datetime import datetime, timezone

import _boot
from autopilot import review


def main() -> int:
    if not review.settings()["enabled"]:
        print("Revisión desactivada en settings.json")
        return 0
    try:
        done = review.sync_issues(datetime.now(timezone.utc))
    except review.ReviewUnavailable as exc:
        print(f"No se pudo crear el issue de revisión: {exc}")
        return 1
    _boot.step_summary("### Revisión\n" + "\n".join(f"- {d}" for d in done or ["sin cambios"]))
    print("\n".join(done))
    return 0


if __name__ == "__main__":
    sys.exit(main())
