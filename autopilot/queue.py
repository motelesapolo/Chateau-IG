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
      "subtext": "Línea secundaria más chica (opcional)",
      "style": "auto" | "title" | "body",      # auto: textos cortos con la tipografía del logo
      "narration": "Lo que dice la voz en off (solo reels/historias de video)",
      "duration": 4,                         # segundos; en un video propio se puede omitir (se usa completo)
      "keep_audio": true                     # video propio: conservar su sonido (si no hay narración)
    }
  ],
  "music": "assets/music/archivo.mp3",       # opcional
  "cover": "material/portadas/archivo.jpg",  # opcional: portada propia del reel (se ajusta a 9:16)
  "collaborators": ["cuenta_aliada"],        # opcional: post en colaboración (hasta 3 cuentas)
  "alt_text": "Descripción de la imagen",    # opcional: accesibilidad y búsqueda (imagen/carrusel)
  "status": "planned"                        # planned → rendered → published
}

Fuentes de `visual`:
  diseno         {"path": "material/...", "estilo": "poster-deco", "brief": "(opcional)"}  (sin "path": pieza solo gráfica)
                 Pieza diseñada por la IA (API de ChatGPT) con la foto REAL puesta tal cual en el hueco que deja.
                 Textos de la escena: "kicker", "text" (título), "subtext", "cta" (se escriben exactos en el diseño).
                 Estilos en config/estilos.json (rotarlos). Sin clave/saldo o si falla: plantilla con marco.
  ia             {"prompt": "...", "quality": "high"}     imagen IA: OpenAI si hay OPENAI_API_KEY, si no Pollinations
  pollinations   {"prompt": "...", "seed": 7}             igual que "ia" (nombre antiguo); "engine": "pollinations" fuerza la gratis
                 Prompts de IA: en inglés, fotográficos y concretos (luz, encuadre, lente, materiales).
                 Nunca para mostrar las habitaciones o el hotel: eso SOLO con "file" (material real).
  pixabay_photo  {"query": "..."}  pixabay_video {"query": "..."}   stock gratis (PIXABAY_KEY)
  pexels_photo   {"query": "..."}  pexels_video  {"query": "..."}   stock gratis (PEXELS_KEY)
  card           {"bg": "rojo", "bg2": "rojo", "logo": true}   fondo con la paleta de la marca para frases.
                 Colores: rojo, crema, beige, arena, dorado, cafe (o #hex). "logo": true pone el logo arriba
                 ("logo_position": "top" | "center" | "bottom"). Sobre fondo claro el texto va en rojo.
  file           {"path": "material/habitaciones/jacuzzi/foto.jpg"}  foto o video real del hotel
                 Fotos: "retoque": "suave" (por defecto, local y gratis) | "fuerte" | "no".
                 "encuadre": "auto" (por defecto) | "recorte" (llena el cuadro) | "marco" (foto completa con
                   borde dorado sobre fondo rojo desenfocado; auto lo usa si recortar dejaría la foto borrosa).
                 "ia_edit": retoque con la API de OpenAI (si hay OPENAI_API_KEY; si falla, queda el local):
                   "luz"   → solo luz y color, conserva todo lo demás. Se puede usar en habitaciones.
                   "fondo" → cambia solo el fondo (comida, tragos, productos). NO en habitaciones/espacios.
                   "<instrucción libre en inglés>" → solo fuera de material/habitaciones y material/espacios.
                 (también sirve assets/...). Para mostrar habitaciones SIEMPRE material propio.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from . import config

TYPES = {"reel", "image", "carousel", "story"}
SOURCES = {"diseno", "ia", "pollinations", "pixabay_photo", "pixabay_video", "pexels_photo", "pexels_video",
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


VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}


def own_video(scene: dict) -> Path | None:
    vis = scene.get("visual") or {}
    if vis.get("source") == "file" and Path(str(vis.get("path", ""))).suffix.lower() in VIDEO_EXT:
        return config.ROOT / vis["path"]
    return None


def _probe(path: Path) -> float:
    import subprocess
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, timeout=30)
        return float(out.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return 4.0


def scene_duration(scene: dict) -> float:
    if scene.get("duration") is None and (video := own_video(scene)) and video.is_file():
        return min(_probe(video), 90.0)
    return float(scene.get("duration", 4))


def total_duration(item: dict) -> float:
    return sum(scene_duration(s) for s in item.get("scenes", []))


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
        if src in {"ia", "pollinations"} and not vis.get("prompt"):
            errs.append(f"escena {i}: {src} necesita prompt")
        if src.startswith(("pixabay", "pexels")) and not vis.get("query"):
            errs.append(f"escena {i}: {src} necesita query")
        if src == "diseno" and not item.get("prueba"):
            errs.append(f"escena {i}: 'diseno' (diseño completo hecho por la IA) no está en la línea editorial; "
                        "usa los formatos de config/linea-editorial.md")
        if src == "diseno":
            import json as _json
            p = config.ROOT / str(vis.get("path", ""))
            if vis.get("path") and not p.is_file():
                errs.append(f"escena {i}: no existe el archivo {vis.get('path')}")
            ecfg = _json.loads((config.CONFIG_DIR / "estilos.json").read_text(encoding="utf-8"))
            ok_styles = ecfg.get("aprobados", list(ecfg["estilos"]))
            if vis.get("estilo") and vis["estilo"] not in ok_styles and not item.get("prueba"):
                errs.append(f"escena {i}: estilo '{vis['estilo']}' no está aprobado por el dueño "
                            f"(aprobados: {', '.join(ok_styles)})")
        if src == "file":
            p = config.ROOT / str(vis.get("path", ""))
            if not p.is_file():
                errs.append(f"escena {i}: no existe el archivo {vis.get('path')}")
            mode = vis.get("ia_edit")
            if mode and mode != "luz" and str(vis.get("path", "")).startswith(("material/habitaciones", "material/espacios")):
                errs.append(f"escena {i}: en habitaciones y espacios solo se permite ia_edit 'luz' "
                            "(no se altera lo que el cliente va a ver)")
            if vis.get("retoque", "suave") not in {"suave", "fuerte", "no", False}:
                errs.append(f"escena {i}: retoque debe ser suave, fuerte o no")
        if src.endswith("_video") and t in {"image", "carousel"}:
            errs.append(f"escena {i}: un {t} no puede usar video")
        if len(scene.get("text", "")) > 140:
            errs.append(f"escena {i}: text muy largo para leerse en pantalla (máx. 140)")
        dur = scene.get("duration", None if own_video(scene) else 4)
        if dur is not None and (not isinstance(dur, (int, float)) or not 1 <= dur <= 90):
            errs.append(f"escena {i}: duration debe estar entre 1 y 90")

    cover = item.get("cover")
    if cover and not (config.ROOT / cover).is_file():
        errs.append(f"no existe la portada {cover}")
    music = item.get("music")
    if music and not (config.ROOT / music).is_file():
        errs.append(f"no existe la música {music}")
    return errs


def is_video(item: dict) -> bool:
    if item["type"] == "reel":
        return True
    if item["type"] == "story":
        s = item["scenes"][0]
        return (bool(s.get("narration")) or s.get("visual", {}).get("source", "").endswith("_video")
                or own_video(s) is not None)
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
