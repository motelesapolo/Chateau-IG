"""La cola de contenido: un archivo JSON por publicación en queue/.

Formato (lo escribe Claude en el lote semanal):

{
  "id": "2026-11-24-reel-desayuno",         # único, solo minúsculas, números y guiones
  "type": "reel" | "image" | "carousel" | "story",
  "publish_at": "2026-11-24T19:30:00-03:00", # con zona horaria
  "caption": "Texto del post con #hashtags", # no aplica a historias
  "scenes": [                                # 1 para image/story, 2-10 carrusel, 2-15 reel
    {
      "visual": {"source": "pollinations", "prompt": "..."},
      "text": "Texto grande sobre la imagen (opcional)",
      "narration": "Lo que dice la voz en off (solo reels/historias de video)",
      "duration": 4                          # segundos (reels/historias de video)
    }
  ],
  "music": "assets/music/archivo.mp3",       # opcional
  "collaborators": ["cuenta_aliada"],        # opcional: post en colaboración (hasta 3 cuentas)
  "alt_text": "Descripción de la imagen",    # opcional: accesibilidad y búsqueda (imagen/carrusel)
  "status": "planned"                        # planned → rendered → published
}

Fuentes de `visual`:
  pollinations   {"prompt": "...", "seed": 7}             imagen IA gratis
  pixabay_photo  {"query": "..."}  pixabay_video {"query": "..."}   stock gratis (PIXABAY_KEY)
  pexels_photo   {"query": "..."}  pexels_video  {"query": "..."}   stock gratis (PEXELS_KEY)
  card           {"bg": "#101820", "bg2": "#2b5876"}      fondo de color/degradado para frases
  file           {"path": "material/habitaciones/jacuzzi/foto.jpg"}  foto o video real del hotel
                 (también sirve assets/...). Para mostrar habitaciones SIEMPRE material propio.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from . import config

TYPES = {"reel", "image", "carousel", "story"}
SOURCES = {"pollinations", "pixabay_photo", "pixabay_video", "pexels_photo", "pexels_video",
           "card", "file"}
STATUSES = {"planned", "rendered", "render_failed", "published", "publish_failed",
            "missed", "cancelled"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")


def parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=config.timezone())
    return dt


def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        item = json.load(fh)
    item.setdefault("status", "planned")
    return item


def save(item: dict, directory: Path | None = None) -> Path:
    directory = directory or config.QUEUE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{item['id']}.json"
    path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def all_items(directory: Path | None = None) -> list[tuple[Path, dict]]:
    directory = directory or config.QUEUE_DIR
    out = []
    for path in sorted(directory.glob("*.json")):
        out.append((path, load(path)))
    return out


def published_ids() -> set[str]:
    return {p.stem for p in config.PUBLISHED_DIR.glob("*.json")}


def total_duration(item: dict) -> float:
    return sum(float(s.get("duration", 4)) for s in item.get("scenes", []))


def validate(item: dict) -> list[str]:
    """Devuelve una lista de errores (vacía si todo está bien)."""
    errs: list[str] = []
    iid = item.get("id", "")
    if not ID_RE.match(str(iid)):
        errs.append(f"id inválido '{iid}' (usa minúsculas, números y guiones)")
    t = item.get("type")
    if t not in TYPES:
        errs.append(f"type debe ser uno de {sorted(TYPES)}")
    if item.get("status", "planned") not in STATUSES:
        errs.append(f"status desconocido: {item.get('status')}")
    try:
        when = parse_time(item.get("publish_at", ""))
        if when.year < 2025:
            errs.append("publish_at parece incorrecto")
    except (ValueError, TypeError):
        errs.append("publish_at debe ser fecha ISO, ej. 2026-11-24T19:30:00-03:00")

    caption = item.get("caption", "")
    if t != "story":
        if not caption.strip():
            errs.append("falta caption")
        if len(caption) > 2200:
            errs.append(f"caption muy largo ({len(caption)} > 2200)")
        tags = re.findall(r"#\w+", caption)
        if len(tags) > 5:
            errs.append(f"máximo 5 hashtags (Instagram limita a 5 desde dic. 2025; hay {len(tags)})")

    scenes = item.get("scenes") or []
    n = len(scenes)
    if t in {"image", "story"} and n != 1:
        errs.append(f"{t} necesita exactamente 1 escena (tiene {n})")
    if t == "carousel" and not 2 <= n <= 10:
        errs.append(f"carousel necesita 2–10 escenas (tiene {n})")
    if t == "reel":
        if not 1 <= n <= 15:
            errs.append(f"reel necesita 1–15 escenas (tiene {n})")
        dur = total_duration(item)
        if not 3 <= dur <= 90:
            errs.append(f"reel debe durar 3–90 s (suma {dur:.0f} s)")
    if t == "story" and total_duration(item) > 60:
        errs.append("una historia de video dura máximo 60 s")

    for i, scene in enumerate(scenes, 1):
        vis = scene.get("visual") or {}
        src = vis.get("source")
        if src not in SOURCES:
            errs.append(f"escena {i}: visual.source debe ser uno de {sorted(SOURCES)}")
            continue
        if src == "pollinations" and not vis.get("prompt"):
            errs.append(f"escena {i}: pollinations necesita prompt")
        if src.startswith(("pixabay", "pexels")) and not vis.get("query"):
            errs.append(f"escena {i}: {src} necesita query")
        if src == "file":
            p = config.ROOT / str(vis.get("path", ""))
            if not p.is_file():
                errs.append(f"escena {i}: no existe el archivo {vis.get('path')}")
        if src.endswith("_video") and t in {"image", "carousel"}:
            errs.append(f"escena {i}: un {t} no puede usar video")
        if len(scene.get("text", "")) > 140:
            errs.append(f"escena {i}: text muy largo para leerse en pantalla (máx. 140)")
        dur = scene.get("duration", 4)
        if not isinstance(dur, (int, float)) or not 1 <= dur <= 30:
            errs.append(f"escena {i}: duration debe estar entre 1 y 30")

    music = item.get("music")
    if music and not (config.ROOT / music).is_file():
        errs.append(f"no existe la música {music}")
    return errs


def is_video(item: dict) -> bool:
    if item["type"] == "reel":
        return True
    if item["type"] == "story":
        s = item["scenes"][0]
        return bool(s.get("narration")) or s.get("visual", {}).get("source", "").endswith("_video")
    return False


def due_items(now: datetime, max_late_hours: float) -> list[tuple[Path, dict, bool]]:
    """Publicaciones renderizadas cuya hora llegó. El bool indica si ya pasaron demasiado tarde."""
    out = []
    for path, item in all_items():
        if item.get("status") != "rendered":
            continue
        when = parse_time(item["publish_at"])
        if when <= now:
            late = now - when > timedelta(hours=max_late_hours)
            out.append((path, item, late))
    out.sort(key=lambda x: parse_time(x[1]["publish_at"]))
    return out
