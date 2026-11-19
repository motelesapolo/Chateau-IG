"""Renderiza las publicaciones pendientes (status "planned") y actualiza la rama media.

Uso: python scripts/render_queue.py [--no-sync] [id ...]
"""
import argparse
import logging
import sys
import traceback

import _boot
from autopilot import config, hosting, render
from autopilot import queue as q

log = logging.getLogger("render")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--no-sync", action="store_true", help="no actualizar la rama media (pruebas)")
    args = ap.parse_args()

    settings = config.load_settings()
    if not args.no_sync:
        restored = hosting.restore()
        log.info("Archivos restaurados desde la rama media: %d", restored)

    done, failed = [], []
    for path, item in q.all_items():
        if args.ids and item["id"] not in args.ids:
            continue
        if item.get("status") != "planned":
            continue
        log.info("Renderizando %s (%s)…", item["id"], item["type"])
        try:
            item["media"] = render.render_item(item, settings)
            item["status"] = "rendered"
            item.pop("error", None)
            done.append(item["id"])
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            item["status"] = "render_failed"
            item["error"] = f"{type(exc).__name__}: {exc}"[:500]
            failed.append(f"{item['id']}: {item['error']}")
        q.save(item)

    if not args.no_sync:
        keep = {i["id"] for _, i in q.all_items() if i.get("status") == "rendered"}
        sha = hosting.sync(keep)
        log.info("Rama media actualizada (%s) con %d publicaciones pendientes", sha, len(keep))

    lines = [f"### Render: {len(done)} listas, {len(failed)} con error"]
    lines += [f"- ✅ {d}" for d in done] + [f"- ❌ {f}" for f in failed]
    _boot.step_summary("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
