"""Convierte fecha/hora local en el formato de publish_at (con la zona horaria correcta, incluido horario de verano).

Uso:
  python scripts/when.py "2026-11-24 19:30"          → 2026-11-24T19:30:00-03:00
  python scripts/when.py --week 2026-11-24            → horarios sugeridos para los 7 días desde esa fecha
"""
import sys
from datetime import date, datetime, timedelta

import _boot  # noqa: F401
from autopilot import config


def iso(local: str) -> str:
    dt = datetime.fromisoformat(local).replace(tzinfo=config.timezone())
    return dt.isoformat()


def week(start: str) -> None:
    plan = config.load_settings().get("weekly_plan", {})
    d0 = date.fromisoformat(start)
    for k in range(7):
        d = d0 + timedelta(days=k)
        times = [plan.get("story_time", "10:00")] + plan.get("post_times", ["19:30"])
        print(d.strftime("%a %Y-%m-%d"), " ".join(iso(f"{d} {t}") for t in times))


if __name__ == "__main__":
    if sys.argv[1] == "--week":
        week(sys.argv[2])
    else:
        print(iso(sys.argv[1]))
