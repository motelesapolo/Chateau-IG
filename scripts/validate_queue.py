"""Revisa que todas las publicaciones de queue/ estén bien escritas.

Uso: python scripts/validate_queue.py [archivo.json ...]
Sale con código 1 si hay errores.
"""
import sys
from pathlib import Path

import _boot  # noqa: F401
from autopilot import config
from autopilot import promos
from autopilot import queue as q


def main(paths: list[str]) -> int:
    files = [Path(p) for p in paths] or sorted(config.QUEUE_DIR.glob("*.json"))
    bad = 0
    seen: dict[str, Path] = {}
    for path in files:
        try:
            item = q.load(path)
        except (ValueError, OSError) as exc:
            print(f"❌ {path.name}: JSON inválido ({exc})")
            bad += 1
            continue
        errs = q.validate(item)
        if item.get("id") and path.stem != item["id"]:
            errs.append(f"el archivo debe llamarse {item['id']}.json")
        if item.get("id") in seen:
            errs.append(f"id repetido (también en {seen[item['id']].name})")
        seen[item.get("id")] = path
        if item.get("id") in q.published_ids():
            errs.append("ese id ya se publicó; usa uno nuevo")
        if errs:
            bad += 1
            print(f"❌ {path.name}")
            for e in errs:
                print(f"   - {e}")
        else:
            print(f"✅ {path.name} ({item['type']}, {item['publish_at']})")
    perrs = promos.validate()
    for e in perrs:
        print(f"❌ config/promos.json: {e}")
    bad += bool(perrs)
    print(f"\n{len(files) - bad}/{len(files)} publicaciones válidas")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
