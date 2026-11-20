"""Sale con código 0 si hay publicaciones listas cuya hora ya llegó (o llega en los próximos minutos).

Lo usa la tarea programada de Claude que cada hora "toca" el repo para que GitHub publique a tiempo
(los horarios automáticos de GitHub se atrasan mucho).
"""
import sys
from datetime import datetime, timedelta, timezone

import _boot  # noqa: F401
from autopilot import queue as q


def main() -> int:
    now = datetime.now(timezone.utc) + timedelta(minutes=10)
    due = [i["id"] for _, i in q.all_items()
           if i.get("status") == "rendered" and q.parse_time(i["publish_at"]) <= now]
    print("\n".join(due) or "nada pendiente")
    return 0 if due else 1


if __name__ == "__main__":
    sys.exit(main())
