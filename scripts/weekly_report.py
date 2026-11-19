"""Informe semanal (lo lee Claude antes de planificar la semana siguiente).

Solo guarda métricas y textos de las publicaciones propias (que ya son públicas) y conteos
de la bandeja. Nunca guarda el contenido de comentarios ni mensajes.

Uso: python scripts/weekly_report.py
"""
import json
import sys
import time
from datetime import datetime, timedelta, timezone

import _boot
from autopilot import config
from autopilot import queue as q
from autopilot.api import client_from_env
from autopilot.inbox import parse_ts


def main() -> int:
    settings = config.load_settings()
    client = client_from_env(settings)
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)
    me = client.me()

    rows = []
    for m in client.list_media(limit=30):
        when = parse_ts(m["timestamp"])
        if when < since:
            continue
        ins = client.media_insights(m["id"])
        rows.append({
            "fecha": when.astimezone(config.timezone()).strftime("%a %d %H:%M"),
            "tipo": m.get("media_product_type") or m.get("media_type"),
            "likes": m.get("like_count", 0), "comentarios": m.get("comments_count", 0),
            "alcance": ins.get("reach", "–"), "vistas": ins.get("views", "–"),
            "guardados": ins.get("saved", "–"), "compartidos": ins.get("shares", "–"),
            "texto": (m.get("caption") or "").split("\n")[0][:80], "link": m.get("permalink", ""),
        })

    inbox_counts: dict[str, int] = {}
    state_file = config.STATE_DIR / "inbox.json"
    if state_file.exists():
        data = json.loads(state_file.read_text())
        cutoff = time.time() - 7 * 86400
        for kind in ("comments", "messages"):
            for v in data.get(kind, {}).values():
                if v["t"] >= cutoff:
                    key = f"{kind}:{v['a']}"
                    inbox_counts[key] = inbox_counts.get(key, 0) + 1

    pending = [i for _, i in q.all_items() if i.get("status") in {"planned", "rendered"}]
    failed = [i for _, i in q.all_items() if i.get("status") in {"render_failed", "publish_failed", "missed"}]

    lines = [f"# Informe semanal — {now.astimezone(config.timezone()):%Y-%m-%d}", "",
             f"Cuenta: @{me.get('username')} · seguidores: {me.get('followers_count', '–')} · "
             f"publicaciones totales: {me.get('media_count', '–')}", "",
             "## Publicaciones de los últimos 7 días", ""]
    if rows:
        lines.append("| Fecha | Tipo | Likes | Coment. | Alcance | Vistas | Guard. | Compart. | Texto |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in sorted(rows, key=lambda r: r["fecha"]):
            lines.append(f"| {r['fecha']} | {r['tipo']} | {r['likes']} | {r['comentarios']} | {r['alcance']} | "
                         f"{r['vistas']} | {r['guardados']} | {r['compartidos']} | [{r['texto']}]({r['link']}) |")
    else:
        lines.append("_Sin publicaciones esta semana._")
    lines += ["", "## Bandeja (últimos 7 días, solo conteos)", ""]
    labels = {"reply": "respondidos", "hide": "ocultados", "skip": "omitidos", "flag": "para revisar en la app",
              "crisis": "crisis (revisar en la app)", "already": "ya tenían respuesta"}
    if inbox_counts:
        for key, n in sorted(inbox_counts.items()):
            kind, action = key.split(":")
            lines.append(f"- {'Comentarios' if kind == 'comments' else 'DMs'} {labels.get(action, action)}: {n}")
    else:
        lines.append("_Sin actividad registrada._")
    lines += ["", "## Cola", "", f"- Pendientes por publicar: {len(pending)}"]
    for i in failed:
        lines.append(f"- ⚠️ {i['id']} ({i['status']}): {i.get('error', '')[:150]}")

    config.REPORTS_DIR.mkdir(exist_ok=True)
    out = config.REPORTS_DIR / f"{now.astimezone(config.timezone()):%Y-%m-%d}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _boot.step_summary("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
