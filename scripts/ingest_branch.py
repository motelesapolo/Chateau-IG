"""Incorpora a main la cola nueva que Claude subió a una rama claude/...

Por seguridad solo copia archivos de queue/ y assets/, y nunca reabre algo ya publicado
o ya renderizado (salvo que la publicación traiga "replace": true).

Uso: python scripts/ingest_branch.py origin/claude/lote-2026-11-23
"""
import json
import subprocess
import sys

import _boot
from autopilot import config
from autopilot import queue as q

KEEP_STATUS = {"planned", "render_failed", "cancelled"}


def git_bytes(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=config.ROOT, capture_output=True, check=True).stdout


def main(ref: str) -> int:
    names = git_bytes("ls-tree", "-r", "--name-only", ref, "--", "queue", "assets", "reviews").decode().splitlines()
    published = q.published_ids()
    added, skipped, invalid, assets = [], [], [], 0

    for name in names:
        # reviews/*.md: mensajes de Claude para el issue de revisión (los publica scripts/review_issue.py)
        if name.startswith("assets/") or (name.startswith("reviews/") and name.endswith(".md")):
            data = git_bytes("show", f"{ref}:{name}")
            dest = config.ROOT / name
            if not dest.exists() or dest.read_bytes() != data:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                assets += 1

    for name in names:
        if not (name.startswith("queue/") and name.endswith(".json")):
            continue
        try:
            item = json.loads(git_bytes("show", f"{ref}:{name}"))
        except ValueError:
            invalid.append(f"{name}: JSON inválido")
            continue
        iid = item.get("id", "")
        if iid in published:
            skipped.append(f"{iid}: ya publicado")
            continue
        current = config.QUEUE_DIR / f"{iid}.json"
        if current.exists():
            cur = q.load(current)
            strip = ("status", "media", "result", "error", "attempts", "replace")
            same = {k: v for k, v in cur.items() if k not in strip} == \
                   {k: v for k, v in item.items() if k not in strip}
            if same and item.get("status") != "cancelled":
                skipped.append(f"{iid}: sin cambios")
                continue
            if cur.get("status") not in KEEP_STATUS and not item.get("replace"):
                skipped.append(f"{iid}: ya renderizado (agrega \"replace\": true para rehacerlo)")
                continue
        errs = q.validate(item)
        if errs:
            invalid.append(f"{iid or name}: " + "; ".join(errs))
            continue
        item.pop("replace", None)
        item.pop("media", None)
        item.pop("result", None)
        item.pop("error", None)
        item["status"] = "cancelled" if item.get("status") == "cancelled" else "planned"
        q.save(item)
        added.append(iid)

    lines = [f"### Cola recibida desde `{ref}`",
             f"- Nuevas o actualizadas: **{len(added)}** {', '.join(added)}",
             f"- Archivos de assets: {assets}",
             f"- Omitidas: {len(skipped)}"]
    lines += [f"  - {s}" for s in skipped]
    if invalid:
        lines.append(f"- ❌ Inválidas (no se incorporaron): {len(invalid)}")
        lines += [f"  - {s}" for s in invalid]
    _boot.step_summary("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
