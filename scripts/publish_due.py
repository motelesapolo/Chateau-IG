"""Publica en Instagram lo que ya está renderizado y cuya hora llegó.

Uso: python scripts/publish_due.py        (DRY_RUN=1 para simular sin publicar)
"""
import json
import logging
import sys
from datetime import datetime, timezone

import _boot
from autopilot import config, hosting, review
from autopilot import queue as q
from autopilot.api import InstagramClient, InstagramError, client_from_env

log = logging.getLogger("publish")


def pick_audio(client: InstagramClient, music: dict) -> tuple[str | None, str]:
    """Resuelve la música pedida: {"audio_id": ...} o {"buscar": "artista canción"}. Devuelve (id, descripción)."""
    if music.get("audio_id"):
        return str(music["audio_id"]), music.get("nombre", music["audio_id"])
    query = (music.get("buscar") or "").strip()
    if not query:
        return None, ""
    try:
        found = client.search_audio(query)
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudo buscar la música '%s': %s", query, exc)
        return None, ""
    words = [w for w in query.lower().split() if len(w) > 2]
    def score(a: dict) -> int:
        text = f"{a.get('title', '')} {a.get('display_artist', '')}".lower()
        return sum(w in text for w in words)
    best = max(found, key=score, default=None)
    if not best or score(best) == 0:
        return None, ""
    return str(best["audio_id"]), f"{best.get('title')} — {best.get('display_artist')}"


def extras(item: dict, settings: dict, client: InstagramClient | None = None) -> dict:
    out = {}
    music = item.get("musica")
    if item.get("type") == "reel" and music and client is not None:
        audio_id, name = pick_audio(client, music)
        if audio_id:
            vol = int(music.get("volumen", 100))
            out["audio_configuration"] = json.dumps({"audio_id": audio_id, "audio_volume": max(1, min(vol, 100))})
            item["musica_usada"] = name
        else:
            item["musica_usada"] = "no encontrada: se publicó sin música"
    if settings.get("location_id"):
        out["location_id"] = str(settings["location_id"])
    if item.get("collaborators"):
        out["collaborators"] = ",".join(str(c).lstrip("@") for c in item["collaborators"][:3])
    if item.get("alt_text"):
        out["alt_text"] = item["alt_text"][:1000]
    return out


def publish_one(client: InstagramClient, item: dict, sha: str, ai: bool, settings: dict | None = None) -> dict:
    media = item["media"]
    extra = extras(item, settings or {}, client)
    urls = [hosting.reachable_url(f, sha) for f in media["files"]]
    caption = item.get("caption", "")
    t = item["type"]
    if t == "image":
        return client.publish_image(urls[0], caption, ai, extra=extra)
    if t == "carousel":
        return client.publish_carousel(urls, caption, ai, extra=extra)
    if t == "reel":
        cover = hosting.reachable_url(media["cover"], sha) if media.get("cover") else None
        return client.publish_reel(urls[0], caption, ai, share_to_feed=item.get("share_to_feed", True),
                                   cover_url=cover, extra=extra)
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
    approvals: dict[str, bool] = {}
    rcfg = review.settings()
    if rcfg["enabled"]:
        try:
            approvals = review.decisions()
        except review.ReviewUnavailable as exc:
            # Sin saber qué aprobó el dueño no se publica: se reintenta en 15 minutos.
            print(f"No se pudo leer la revisión ({exc}); se reintenta en la próxima vuelta.")
            return 0
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
        if rcfg["enabled"]:
            approved = approvals.get(item["id"], rcfg["default"] == "approve")
            if not approved:
                item["status"] = "cancelled"
                item["error"] = "No aprobada en la revisión semanal."
                q.save(item)
                results.append(f"- 🚫 {item['id']}: desmarcada en la revisión, no se publica")
                continue
        try:
            if dry:
                urls = [hosting.reachable_url(f, sha) for f in item["media"]["files"]]
                results.append(f"- 🧪 {item['id']}: se publicaría {urls}")
                continue
            label = item.get("ai_generated", q.uses_generated_images(item)) if ai else False
            info = publish_one(client, item, sha, label, settings)
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
