"""Publica en Instagram lo que ya está renderizado y cuya hora llegó.

Uso: python scripts/publish_due.py        (DRY_RUN=1 para simular sin publicar)
"""
import logging
import sys
from datetime import datetime, timezone

import _boot
from autopilot import config, hosting
from autopilot import queue as q
from autopilot.api import InstagramClient, InstagramError, client_from_env

log = logging.getLogger("publish")


def publish_one(client: InstagramClient, item: dict, sha: str, ai: bool) -> dict:
    media = item["media"]
    urls = [hosting.reachable_url(f, sha) for f in media["files"]]
    caption = item.get("caption", "")
    t = item["type"]
    if t == "image":
        return client.publish_image(urls[0], caption, ai)
    if t == "carousel":
        return client.publish_carousel(urls, caption, ai)
    if t == "reel":
        cover = hosting.reachable_url(media["cover"], sha) if media.get("cover") else None
        return client.publish_reel(urls[0], caption, ai, share_to_feed=item.get("share_to_feed", True),
                                   cover_url=cover)
    if t == "story":
        if media["kind"] == "video":
            return client.publish_story(video_url=urls[0], ai_generated=ai)
        return client.publish_story(image_url=urls[0], ai_generated=ai)
    raise ValueError(f"tipo desconocido {t}")


def main() -> int:
    settings = config.load_settings()
    pub = settings.get("publishing", {})
    now = datetime.now(timezone.utc)
    due = q.due_items(now, pub.get("max_late_hours", 20))
    if not due:
        print("Nada que publicar por ahora.")
        return 0

    dry = config.dry_run()
    client = client_from_env(settings)
    sha = hosting.media_sha()
    if not sha:
        print("No existe la rama media todavía: falta renderizar.")
        return 1
    ai = bool(settings.get("ai_generated_label", True))
    results = []
    count = 0
    for path, item, late in due:
        if late:
            item["status"] = "missed"
            item["error"] = "Se pasó la hora por más de max_late_hours; no se publicó."
            q.save(item)
            results.append(f"- ⏭️ {item['id']}: muy atrasada, se omitió")
            continue
        if count >= pub.get("max_posts_per_run", 2):
            break
        try:
            if dry:
                urls = [hosting.reachable_url(f, sha) for f in item["media"]["files"]]
                results.append(f"- 🧪 {item['id']}: se publicaría {urls}")
                continue
            info = publish_one(client, item, sha, ai)
            item["status"] = "published"
            item["result"] = {"media_id": info.get("id"), "permalink": info.get("permalink"),
                              "published_at": now.isoformat()}
            item.pop("error", None)
            q.save(item, config.PUBLISHED_DIR)
            path.unlink()
            results.append(f"- ✅ {item['id']} → {info.get('permalink', info.get('id'))}")
            count += 1
        except (InstagramError, RuntimeError, ValueError) as exc:
            rate_limited = getattr(exc, "is_rate_limit", False)
            item["attempts"] = item.get("attempts", 0) + (0 if rate_limited else 1)
            # Se reintenta en la siguiente vuelta (15 min) hasta 3 veces.
            item["status"] = "rendered" if rate_limited or item["attempts"] < 3 else "publish_failed"
            item["error"] = str(exc)[:500]
            q.save(item)
            results.append(f"- ❌ {item['id']} (intento {item['attempts']}): {exc}")
            if rate_limited:
                break
    _boot.step_summary("### Publicación\n" + "\n".join(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
