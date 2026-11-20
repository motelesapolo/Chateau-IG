"""Convierte una publicación de la cola en archivos listos para Instagram.

- Imágenes de feed: JPG 1080x1350 (4:5).
- Reels e historias de video: MP4 H.264/AAC 1080x1920, 30 fps, < 19 MB.
- Historias de imagen: JPG 1080x1920.

Imágenes IA: OpenAI (gpt-image) si existe el secreto OPENAI_API_KEY; si no, o si falla, Pollinations (gratis).
Stock de Pixabay/Pexels, voz de edge-tts y montaje con ffmpeg + Pillow.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import config
from . import queue as q

log = logging.getLogger(__name__)

FEED = (1080, 1350)
VERTICAL = (1080, 1920)
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}
MAX_VIDEO_MB = 19.0
UA = {"User-Agent": "ig-autopilot/1.0 (+https://github.com)"}

_last_pollinations = 0.0
_openai_count = 0
last_engine = ""  # qué motor generó/retocó la última imagen (para pruebas e informes)
OPENAI_DEFAULTS = {"model": "gpt-image-2", "fallback_models": ["gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"],
                   "edit_models": ["gpt-image-2", "gpt-image-1.5", "gpt-image-1"],
                   "quality": "medium", "max_per_run": 40}

# Retoque con IA de fotos REALES. "luz" se puede usar en cualquier foto (incluidas habitaciones);
# "fondo" y las instrucciones libres solo fuera de habitaciones/espacios (no se altera lo que el cliente va a ver).
PRESERVE = ("Keep everything else exactly the same: every object, furniture, bed, bathtub, walls, artwork, "
            "curtains, lamps, materials, textures, proportions, room size, layout and camera angle. "
            "Do not add, remove, move or resize anything. No people, no text, no logos.")
EDIT_PRESETS = {
    "luz": ("Retouch this real hotel photo like a professional hotel photographer: correct exposure and white "
            "balance, warm inviting tungsten tone, recover shadows and highlights, gentle contrast and clarity, "
            "subtle sharpening. Change ONLY light and color. " + PRESERVE),
    "fondo": ("Keep the main subject (food, drink or product) pixel-identical in shape, portion, color and "
              "plating. Replace only the background and surface with an elegant warm setting in deep burgundy, "
              "cream and muted gold tones with soft candlelight bokeh. Professional food photography lighting. "
              "No people, no text, no logos."),
}
PROTECTED_DIRS = ("material/habitaciones", "material/espacios")


class RenderError(RuntimeError):
    pass


# ----------------------------------------------------------------- utilidades
def run(cmd: list[str]) -> None:
    log.debug("$ %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RenderError(f"ffmpeg falló: {proc.stderr[-1500:]}")


def media_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def seed_for(item_id: str, idx: int) -> int:
    return int(hashlib.sha1(f"{item_id}:{idx}".encode()).hexdigest()[:8], 16) % 1_000_000


def download(url: str, dest: Path, headers: dict | None = None, tries: int = 3) -> Path:
    last = None
    for attempt in range(tries):
        try:
            with requests.get(url, headers={**UA, **(headers or {})}, timeout=180, stream=True) as r:
                r.raise_for_status()
                with open(dest, "wb") as fh:
                    for chunk in r.iter_content(1 << 16):
                        fh.write(chunk)
            if dest.stat().st_size < 1000:
                raise RenderError(f"Descarga demasiado pequeña desde {url}")
            return dest
        except (requests.RequestException, RenderError) as exc:
            last = exc
            time.sleep(5 * (attempt + 1))
    raise RenderError(f"No se pudo descargar {url}: {last}")


# -------------------------------------------------------------------- fuentes
def _pollinations(vis: dict, size: tuple[int, int], dest: Path, seed: int) -> Path:
    global _last_pollinations
    wait = 16 - (time.time() - _last_pollinations)  # anónimo: ~1 imagen cada 15 s
    if wait > 0 and not os.environ.get("POLLINATIONS_TOKEN"):
        time.sleep(wait)
    # Se pide un 8% más alto para recortar abajo la marca de agua del plan anónimo.
    params = {"width": size[0], "height": int(size[1] * 1.08), "seed": vis.get("seed", seed),
              "nologo": "true", "model": vis.get("model", "flux")}
    headers = {}
    if os.environ.get("POLLINATIONS_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['POLLINATIONS_TOKEN']}"
    url = f"https://image.pollinations.ai/prompt/{quote(branded_prompt(vis))}"
    last = None
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, headers={**UA, **headers}, timeout=240)
            _last_pollinations = time.time()
            if r.status_code == 429:
                time.sleep(20 * (attempt + 1))
                continue
            r.raise_for_status()
            img = Image.open(BytesIO(r.content)).convert("RGB")
            cut = int(img.height * 0.075)
            img.crop((0, 0, img.width, img.height - cut)).save(dest, quality=95)
            return dest
        except Exception as exc:  # noqa: BLE001 - cualquier fallo se reintenta
            last = exc
            time.sleep(10 * (attempt + 1))
    raise RenderError(f"Pollinations no generó la imagen: {last}")


def _model_unavailable(r) -> bool:
    """El modelo no existe o la cuenta no tiene acceso (p. ej. falta verificar la organización): probar el siguiente."""
    text = r.text.lower()
    if r.status_code == 403 and ("verif" in text or "model" in text):
        return True
    return r.status_code in (400, 404) and "model" in text and "prompt" not in text


def branded_prompt(vis: dict) -> str:
    """Agrega el estilo de la marca a cada pedido de imagen IA (se omite con "brand_style": false)."""
    style = brand().get("ai_style", "")
    if vis.get("brand_style") is False or not style:
        return vis["prompt"]
    return f"{vis['prompt'].rstrip('. ')}. {style}"


def _openai(vis: dict, size: tuple[int, int], dest: Path, session=None) -> Path:
    """Genera con la API de imágenes de OpenAI y recorta al tamaño de Instagram."""
    global _openai_count
    cfg = {**OPENAI_DEFAULTS, **(config.load_settings().get("openai_images") or {})}
    if _openai_count >= int(cfg["max_per_run"]):
        raise RenderError("Tope de imágenes OpenAI por ejecución alcanzado")
    http = session or requests
    headers = {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"}
    portrait = size[1] > size[0]
    last = None
    for model in [cfg["model"], *cfg["fallback_models"]]:
        body = {"model": model, "prompt": branded_prompt(vis), "n": 1, "quality": vis.get("quality", cfg["quality"]),
                "size": "1024x1536" if portrait else "1024x1024", "output_format": "jpeg"}
        r = http.post("https://api.openai.com/v1/images/generations", headers=headers, json=body, timeout=300)
        if _model_unavailable(r):
            last = f"{model}: {r.status_code}"
            continue  # modelo no disponible para esta cuenta: probar el siguiente
        if r.status_code >= 400:
            raise RenderError(f"OpenAI respondió {r.status_code}: {r.text[:300]}")
        data = r.json()["data"][0]
        if data.get("b64_json"):
            import base64
            raw = base64.b64decode(data["b64_json"])
        else:
            raw = http.get(data["url"], timeout=120).content
        _openai_count += 1
        global last_engine
        last_engine = f"OpenAI {model}"
        img = Image.open(BytesIO(raw)).convert("RGB")
        ImageOps.fit(img, size, Image.LANCZOS).save(dest, quality=95)
        log.info("Imagen IA generada con OpenAI (%s)", model)
        return dest
    raise RenderError(f"Ningún modelo de OpenAI disponible ({last})")


def retouch(img: Image.Image, level: str = "suave") -> Image.Image:
    """Retoque local, gratis y fiel: niveles, calidez, color y nitidez. No cambia el contenido."""
    from PIL import ImageEnhance, ImageFilter
    if level in (False, "no", "none", None):
        return img
    strong = level == "fuerte"
    img = ImageOps.autocontrast(img.convert("RGB"), cutoff=0.6 if strong else 0.3, preserve_tone=True)
    r, g, b = img.split()
    warm = 1.04 if strong else 1.025
    r = r.point(lambda v: min(255, int(v * warm)))
    b = b.point(lambda v: int(v / warm))
    img = Image.merge("RGB", (r, g, b))
    img = ImageEnhance.Color(img).enhance(1.10 if strong else 1.05)
    img = ImageEnhance.Contrast(img).enhance(1.06 if strong else 1.03)
    return img.filter(ImageFilter.UnsharpMask(radius=1.4, percent=70 if strong else 50, threshold=2))


def edit_allowed(path: str, mode: str) -> bool:
    return mode == "luz" or not str(path).startswith(PROTECTED_DIRS)


def _openai_edit(src: Path, instruction: str, dest: Path, portrait: bool, session=None) -> Path:
    """Edita una foto real con la API de imágenes de OpenAI (alta fidelidad a la original)."""
    global _openai_count
    cfg = {**OPENAI_DEFAULTS, **(config.load_settings().get("openai_images") or {})}
    if _openai_count >= int(cfg["max_per_run"]):
        raise RenderError("Tope de imágenes OpenAI por ejecución alcanzado")
    http = session or requests
    buf = BytesIO()
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    im.thumbnail((2048, 2048))
    im.save(buf, "JPEG", quality=92)
    last = None
    for model in cfg["edit_models"]:
        data = {"model": model, "prompt": instruction, "n": "1", "quality": "high", "input_fidelity": "high",
                "size": "1024x1536" if portrait else "1024x1024", "output_format": "jpeg"}
        r = http.post("https://api.openai.com/v1/images/edits",
                      headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                      data=data, files={"image[]": ("foto.jpg", buf.getvalue(), "image/jpeg")}, timeout=300)
        if _model_unavailable(r):
            last = f"{model}: {r.status_code}"
            continue
        if r.status_code >= 400:
            raise RenderError(f"OpenAI (edición) respondió {r.status_code}: {r.text[:300]}")
        import base64
        out = r.json()["data"][0]
        raw = base64.b64decode(out["b64_json"]) if out.get("b64_json") else http.get(out["url"], timeout=120).content
        _openai_count += 1
        global last_engine
        last_engine = f"OpenAI {model}"
        Image.open(BytesIO(raw)).convert("RGB").save(dest, quality=95)
        log.info("Foto retocada con OpenAI (%s)", model)
        return dest
    raise RenderError(f"Ningún modelo de edición disponible ({last})")


def prepare_photo(vis: dict, size: tuple[int, int], workdir: Path, seed: int) -> Path:
    """Foto propia: retoque con IA si se pidió (y hay clave) + retoque local suave. Si la IA falla, queda el local."""
    path = config.ROOT / vis["path"]
    mode = vis.get("ia_edit")
    if mode and os.environ.get("OPENAI_API_KEY"):
        if not edit_allowed(vis["path"], mode if mode in EDIT_PRESETS else "libre"):
            log.warning("ia_edit '%s' no se permite en %s (solo 'luz'); se usa retoque local", mode, vis["path"])
        else:
            instruction = EDIT_PRESETS.get(mode) or f"{mode}. {PRESERVE}"
            try:
                path = _openai_edit(path, instruction, workdir / f"edit_{seed}.jpg", size[1] > size[0])
            except Exception as exc:  # noqa: BLE001
                log.warning("No se pudo retocar con OpenAI (%s); se usa retoque local", exc)
    level = vis.get("retoque", "suave")
    if level in (False, "no"):
        return path
    out = workdir / f"ret_{seed}.jpg"
    retouch(ImageOps.exif_transpose(Image.open(path)), level).save(out, quality=95)
    return out


def ai_image(vis: dict, size: tuple[int, int], dest: Path, seed: int) -> Path:
    """OpenAI si hay clave (mejor calidad); si no hay o falla, Pollinations."""
    if os.environ.get("OPENAI_API_KEY") and vis.get("engine", "auto") != "pollinations":
        try:
            return _openai(vis, size, dest)
        except Exception as exc:  # noqa: BLE001
            log.warning("OpenAI no generó la imagen (%s); se usa Pollinations", exc)
    global last_engine
    last_engine = "Pollinations (gratis)"
    return _pollinations(vis, size, dest, seed)


def _pick(items: list, seed: int):
    if not items:
        return None
    return items[seed % min(len(items), 5)]


def _pixabay(vis: dict, kind: str, dest_dir: Path, seed: int) -> Path:
    key = config.env("PIXABAY_KEY")
    if kind == "photo":
        r = requests.get("https://pixabay.com/api/", params={
            "key": key, "q": vis["query"], "image_type": "photo", "safesearch": "true",
            "orientation": vis.get("orientation", "vertical"), "per_page": 20}, timeout=60)
        r.raise_for_status()
        hit = _pick(r.json().get("hits", []), seed)
        if not hit:
            raise RenderError(f"Pixabay no encontró fotos para '{vis['query']}'")
        return download(hit["largeImageURL"], dest_dir / f"pixabay_{hit['id']}.jpg")
    r = requests.get("https://pixabay.com/api/videos/", params={
        "key": key, "q": vis["query"], "safesearch": "true", "per_page": 20}, timeout=60)
    r.raise_for_status()
    hits = r.json().get("hits", [])
    vertical = [h for h in hits if h["videos"]["medium"].get("height", 0) > h["videos"]["medium"].get("width", 1)]
    hit = _pick(vertical or hits, seed)
    if not hit:
        raise RenderError(f"Pixabay no encontró videos para '{vis['query']}'")
    url = (hit["videos"].get("large") or {}).get("url") or hit["videos"]["medium"]["url"]
    return download(url, dest_dir / f"pixabay_{hit['id']}.mp4")


def _pexels(vis: dict, kind: str, dest_dir: Path, seed: int) -> Path:
    headers = {"Authorization": config.env("PEXELS_KEY")}
    if kind == "photo":
        r = requests.get("https://api.pexels.com/v1/search", headers=headers, params={
            "query": vis["query"], "orientation": vis.get("orientation", "portrait"), "per_page": 15},
            timeout=60)
        r.raise_for_status()
        hit = _pick(r.json().get("photos", []), seed)
        if not hit:
            raise RenderError(f"Pexels no encontró fotos para '{vis['query']}'")
        return download(hit["src"]["large2x"], dest_dir / f"pexels_{hit['id']}.jpg")
    r = requests.get("https://api.pexels.com/videos/search", headers=headers, params={
        "query": vis["query"], "orientation": "portrait", "per_page": 15}, timeout=60)
    r.raise_for_status()
    hit = _pick(r.json().get("videos", []), seed)
    if not hit:
        raise RenderError(f"Pexels no encontró videos para '{vis['query']}'")
    files = [f for f in hit["video_files"] if f.get("height") and f["height"] <= 1920]
    best = max(files or hit["video_files"], key=lambda f: f.get("height") or 0)
    return download(best["link"], dest_dir / f"pexels_{hit['id']}.mp4")


def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _card(vis: dict, size: tuple[int, int], dest: Path) -> Path:
    """Fondo liso o degradado con la paleta de la marca; `logo: true` agrega el logo arriba."""
    bg = vis.get("bg", brand()["card_bg"])
    top, bottom = color(bg), color(vis.get("bg2", bg))
    w, h = size
    grad = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        grad.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    img = grad.resize((w, h))
    if vis.get("logo"):
        logo_file = config.ROOT / brand()["logo"]
        if logo_file.is_file():
            logo = Image.open(logo_file).convert("RGBA")
            if is_light(bg):  # sobre fondo claro, el logo va en rojo
                tint = Image.new("RGBA", logo.size, (*color("rojo"), 255))
                tint.putalpha(logo.getchannel("A"))
                logo = tint
            logo.thumbnail((int(w * 0.46), int(h * 0.2)), Image.LANCZOS)
            pos = vis.get("logo_position", "top")
            ly = {"top": int(h * 0.07), "center": (h - logo.height) // 2}.get(pos, h - logo.height - int(h * 0.06))
            img.paste(logo, ((w - logo.width) // 2, ly), logo)
    img.save(dest, quality=95)
    return dest


def fetch_visual(vis: dict, size: tuple[int, int], workdir: Path, seed: int) -> tuple[Path, str]:
    """Descarga/genera el visual. Devuelve (ruta, 'image'|'video')."""
    src = vis["source"]
    if src in {"pollinations", "ia"}:
        return ai_image(vis, size, workdir / f"ai_{seed}.jpg", seed), "image"
    if src in {"pixabay_photo", "pixabay_video"}:
        kind = src.split("_")[1]
        return _pixabay(vis, kind, workdir, seed), "image" if kind == "photo" else "video"
    if src in {"pexels_photo", "pexels_video"}:
        kind = src.split("_")[1]
        return _pexels(vis, kind, workdir, seed), "image" if kind == "photo" else "video"
    if src == "card":
        return _card(vis, size, workdir / f"card_{seed}.jpg"), "image"
    if src == "file":
        path = config.ROOT / vis["path"]
        if path.suffix.lower() in VIDEO_EXT:
            return path, "video"
        return prepare_photo(vis, size, workdir, seed), "image"
    raise RenderError(f"Fuente desconocida: {src}")


# ---------------------------------------------------------------------- texto
_FONT_CACHE: dict[tuple, ImageFont.FreeTypeFont] = {}
BRAND_DEFAULTS = {
    "colors": {"rojo": "#811721", "crema": "#FCF1E1", "beige": "#F3D8B9", "arena": "#F5DFC5",
               "dorado": "#9C6A2B", "cafe": "#2A1C14"},
    "title_font": "TulpenOne-Regular.ttf", "title_weight": None, "title_stroke": 0.022, "title_tracking": 0.07,
    "body_font": "Manrope[wght].ttf", "body_weight": "SemiBold",
    "box": "rojo", "box_alpha": 185, "text": "crema", "text_on_light": "rojo", "accent": "dorado",
    "card_bg": "rojo", "logo": "assets/brand/logo_crema.png",
    "ai_style": ("Editorial boutique-hotel photography, warm tungsten and candlelight, deep burgundy red, "
                 "warm cream, soft beige and muted gold palette, shallow depth of field, elegant and intimate "
                 "but never sexual, no people, no text, no logos."),
}


def brand() -> dict:
    try:
        custom = config.load_settings().get("brand") or {}
    except Exception:  # noqa: BLE001
        custom = {}
    out = {**BRAND_DEFAULTS, **custom}
    out["colors"] = {**BRAND_DEFAULTS["colors"], **(custom.get("colors") or {})}
    return out


def color(value: str | None, default: str = "crema") -> tuple[int, int, int]:
    """Acepta un nombre de la paleta (rojo, crema, beige, dorado...) o un #hex."""
    value = value or default
    return _hex(brand()["colors"].get(value, value))


def font_path(role: str = "body") -> str | None:
    fonts = config.ASSETS_DIR / "fonts"
    wanted = brand().get(f"{role}_font")
    if wanted and (fonts / wanted).is_file():
        return str(fonts / wanted)
    for pattern, must in (("Montserrat:style=ExtraBold", "montserrat"),
                          ("Montserrat:style=Bold", "montserrat"),
                          ("DejaVu Sans:style=Bold", "dejavu")):
        try:
            out = subprocess.run(["fc-match", "-f", "%{file}", pattern], capture_output=True,
                                 text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            out = ""
        if out and must in out.lower() and Path(out).is_file():
            return out
    return None


def get_font(size: int, role: str = "body"):
    key = (size, role)
    if key not in _FONT_CACHE:
        path = font_path(role)
        font = ImageFont.truetype(path, size) if path else ImageFont.load_default(size)
        # Fuentes variables: forzar el peso de la marca (o uno grueso y legible).
        try:
            names = [n.decode() if isinstance(n, bytes) else n for n in font.get_variation_names()]
            for wanted in (brand().get(f"{role}_weight"), "SemiBold", "Bold", "ExtraBold"):
                if wanted and wanted in names:
                    font.set_variation_by_name(wanted)
                    break
        except (OSError, AttributeError):
            pass
        _FONT_CACHE[key] = font
    return _FONT_CACHE[key]


_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
                       "‍️⭐⬆↔-⇿]+")


def clean_overlay_text(text: str) -> str:
    """Los emojis no se pueden dibujar con la tipografía del texto: se quitan (en el caption sí van)."""
    return re.sub(r"[ \t]{2,}", " ", _EMOJI_RE.sub("", text or "")).strip()


def is_light(value: str) -> bool:
    r, g, b = color(value)
    return (0.299 * r + 0.587 * g + 0.114 * b) > 160


def _tracked_len(line: str, font, tracking: float) -> float:
    return font.getlength(line) + max(len(line) - 1, 0) * tracking


def _wrap(text: str, font, max_width: int, tracking: float = 0.0) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words, cur = paragraph.split(), ""
        for word in words:
            trial = f"{cur} {word}".strip()
            if _tracked_len(trial, font, tracking) <= max_width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def _draw_line(draw, x: float, y: float, line: str, font, fill, tracking: float, stroke: int,
               stroke_fill) -> None:
    if not tracking:
        draw.text((x, y), line, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        return
    for ch in line:
        draw.text((x, y), ch, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        x += font.getlength(ch) + tracking


def _fit_block(text: str, role: str, start: int, max_w: int, max_lines: int, min_size: int):
    b = brand()
    fsize = start
    while True:
        font = get_font(fsize, role)
        tracking = fsize * b["title_tracking"] if role == "title" else 0.0
        lines = _wrap(text, font, max_w, tracking)
        if (len(lines) <= max_lines and all(_tracked_len(l, font, tracking) <= max_w for l in lines)) \
                or fsize <= min_size:
            return font, fsize, tracking, lines
        fsize -= 6


def text_overlay(text: str, size: tuple[int, int], position: str = "center",
                 boxed: bool = True, dark_text: bool = False, subtext: str = "",
                 style: str = "auto", divider: bool = False) -> Image.Image:
    """PNG transparente con el texto en el estilo de la marca.

    - Títulos cortos (<= 48 letras): tipografía de títulos (art déco), en mayúsculas y espaciada.
    - Textos largos o `style: "body"`: tipografía simple.
    - `subtext`: línea secundaria más chica con la tipografía simple.
    """
    b = brand()
    w, h = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    text, subtext = clean_overlay_text(text), clean_overlay_text(subtext)
    if not text and not subtext:
        return layer
    role = style if style in {"title", "body"} else ("title" if len(text) <= 48 else "body")
    if role == "title":
        text = text.upper()
    max_w = int(w * 0.80)
    blocks = []
    if text:
        start = (190 if len(text) < 18 else 160 if len(text) < 32 else 130) if role == "title" else \
                (80 if len(text) < 80 else 64)
        font, fsize, tracking, lines = _fit_block(text, role, start, max_w, 4 if role == "title" else 6, 44)
        stroke = max(1, int(fsize * b["title_stroke"])) if role == "title" else 0
        blocks.append((font, fsize, tracking, lines, stroke, 1.02 if role == "title" else 1.15))
    if subtext:
        font, fsize, tracking, lines = _fit_block(subtext, "body", 52, max_w, 3, 34)
        blocks.append((font, fsize, 0.0, lines, 0, 1.2))
    gap = 28 if len(blocks) == 2 else 0
    heights = []
    for font, fsize, tracking, lines, stroke, lh in blocks:
        ascent, descent = font.getmetrics()
        heights.append(int((ascent + descent) * lh))
    block_h = sum(hgt * len(bl[3]) for hgt, bl in zip(heights, blocks)) + gap + (40 if divider else 0)
    block_w = max(int(_tracked_len(l, bl[0], bl[2])) for bl in blocks for l in bl[3])
    centers = {"top": 0.20, "upper": 0.30, "center": 0.50, "lower": 0.72, "bottom": 0.78}
    cy = int(h * centers.get(position, 0.5))
    y = max(int(h * 0.10), cy - block_h // 2)
    draw = ImageDraw.Draw(layer)
    if boxed:
        pad = 46
        draw.rounded_rectangle([(w - block_w) // 2 - pad, y - pad, (w + block_w) // 2 + pad, y + block_h + pad],
                               radius=28, fill=(*color(b["box"]), int(b["box_alpha"])))
    main = color(b["text_on_light"] if dark_text else b["text"])
    second = color("cafe") if dark_text else main
    for k, ((font, fsize, tracking, lines, stroke, _), lh) in enumerate(zip(blocks, heights)):
        if k == 1:
            y += gap
        fill = (*(main if k == 0 and text else second), 255)
        for line in lines:
            lw = _tracked_len(line, font, tracking)
            _draw_line(draw, (w - lw) / 2, y, line, font, fill, tracking, stroke, fill)
            y += lh
        if k == 0 and divider:
            gold = (*color(b["accent"]), 255)
            y += 14
            half = min(block_w, int(w * 0.5)) // 2
            draw.line([(w / 2 - half, y), (w / 2 + half, y)], fill=gold, width=3)
            draw.polygon([(w / 2, y - 8), (w / 2 + 8, y), (w / 2, y + 8), (w / 2 - 8, y)], fill=gold)
            y += 26
    return layer


def overlay_for(scene: dict, size: tuple[int, int]) -> Image.Image:
    vis = scene["visual"]
    is_card = vis["source"] == "card"
    bg = vis.get("bg", brand()["card_bg"])
    dark = is_card and is_light(bg) and is_light(vis.get("bg2", bg))
    return text_overlay(scene.get("text", ""), size, default_position(scene, size),
                        boxed=not is_card, dark_text=dark, subtext=scene.get("subtext", ""),
                        style=scene.get("style", "auto"), divider=is_card and bool(scene.get("text")))


def default_position(scene: dict, size: tuple[int, int]) -> str:
    if scene.get("text_position"):
        return scene["text_position"]
    if scene["visual"]["source"] == "card":
        vis = scene["visual"]
        if vis.get("logo") and vis.get("logo_position", "top") == "bottom":
            return "upper"
        return "center"
    return "upper" if size == VERTICAL else "lower"


def compose_still(src: Path, scene: dict, size: tuple[int, int], dest: Path) -> Path:
    img = Image.open(src)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, size, Image.LANCZOS, centering=(0.5, 0.4))
    out = Image.alpha_composite(img.convert("RGBA"), overlay_for(scene, size)).convert("RGB")
    out.save(dest, "JPEG", quality=92, optimize=True)
    return dest


# ---------------------------------------------------------------------- voz
def tts(text: str, voice: str, rate: str, dest: Path) -> Path | None:
    if not text.strip() or os.environ.get("DISABLE_TTS"):
        return None
    prefix = shlex.split(os.environ["TTS_CMD"]) if os.environ.get("TTS_CMD") else [sys.executable, "-m", "edge_tts"]
    cmd = [*prefix, "--voice", voice, f"--rate={rate}", "--text", text, "--write-media", str(dest)]
    for attempt in range(3):
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0 and dest.exists() and dest.stat().st_size > 1000:
            return dest
        log.warning("edge-tts falló (intento %d): %s", attempt + 1, proc.stderr[-300:])
        time.sleep(4)
    log.warning("Sin voz para esta escena; se usa silencio.")
    return None


# -------------------------------------------------------------------- video
def has_audio(path: Path) -> bool:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return bool(out.stdout.strip())


def scene_clip(src: Path, kind: str, overlay_png: Path, audio: Path | None, duration: float,
               dest: Path, zoom_in: bool = True, keep_audio: bool = False) -> Path:
    w, h = VERTICAL
    frames = int(round(duration * 30))
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if kind == "image":
        fitted = dest.with_suffix(".fit.jpg")
        img = ImageOps.fit(ImageOps.exif_transpose(Image.open(src)).convert("RGB"), VERTICAL,
                           Image.LANCZOS, centering=(0.5, 0.4))
        img.save(fitted, quality=94)
        z = f"min(1+0.10*on/{frames},1.10)" if zoom_in else f"max(1.10-0.10*on/{frames},1.0)"
        cmd += ["-loop", "1", "-framerate", "30", "-t", f"{duration:.3f}", "-i", str(fitted)]
        vchain = (f"[0:v]scale={w * 2}:{h * 2},zoompan=z='{z}':x='iw/2-(iw/zoom/2)':"
                  f"y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps=30,setsar=1,format=yuv420p[bg]")
    else:
        cmd += ["-stream_loop", "-1", "-i", str(src)]
        vchain = (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
                  f"fps=30,setsar=1,format=yuv420p[bg]")
    cmd += ["-i", str(overlay_png)]
    if audio:
        cmd += ["-i", str(audio)]
        achain = "[2:a]aresample=44100,aformat=channel_layouts=stereo,apad[a]"
    elif keep_audio and kind == "video" and has_audio(src):
        cmd += ["-f", "lavfi", "-t", f"{duration:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
        achain = "[0:a]aresample=44100,aformat=channel_layouts=stereo,apad[a]"
    else:
        cmd += ["-f", "lavfi", "-t", f"{duration:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
        achain = "[2:a]anull[a]"
    filt = f"{vchain};[bg][1:v]overlay=0:0,format=yuv420p[v];{achain}"
    cmd += ["-filter_complex", filt, "-map", "[v]", "-map", "[a]", "-t", f"{duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "30",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", str(dest)]
    run(cmd)
    return dest


def finalize_video(clips: list[Path], music: Path | None, music_volume: float, dest: Path,
                   workdir: Path) -> Path:
    listing = workdir / "concat.txt"
    listing.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips))
    joined = workdir / "joined.mp4"
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", str(joined)])
    dur = media_duration(joined) or 1.0
    kbps = min(5000, int(MAX_VIDEO_MB * 8 * 1024 / dur) - 200)
    for factor in (1.0, 0.7, 0.5):
        br = max(800, int(kbps * factor))
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(joined)]
        if music:
            cmd += ["-stream_loop", "-1", "-i", str(music), "-filter_complex",
                    f"[1:a]volume={music_volume},aresample=44100,aformat=channel_layouts=stereo[m];"
                    f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
                    "-map", "0:v", "-map", "[a]"]
        else:
            cmd += ["-map", "0:v", "-map", "0:a"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-maxrate", f"{br}k",
                "-bufsize", f"{br * 2}k", "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
                "-r", "30", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
                "-movflags", "+faststart", "-t", f"{dur:.3f}", str(dest)]
        run(cmd)
        if dest.stat().st_size / 1e6 <= MAX_VIDEO_MB:
            return dest
        log.info("Video de %.1f MB, se recomprime", dest.stat().st_size / 1e6)
    raise RenderError("No se logró dejar el video bajo 19 MB")


def frame_at(video: Path, t: float, dest: Path) -> Path:
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video),
         "-frames:v", "1", "-q:v", "3", str(dest)])
    return dest


def contact_sheet(images: list[Path], dest: Path, title: str) -> Path:
    thumbs = []
    for p in images:
        im = Image.open(p).convert("RGB")
        im.thumbnail((360, 640))
        thumbs.append(im)
    cols = min(len(thumbs), 5)
    rows = (len(thumbs) + cols - 1) // cols
    cw = max(t.width for t in thumbs)
    ch = max(t.height for t in thumbs)
    sheet = Image.new("RGB", (cols * (cw + 12) + 12, rows * (ch + 12) + 70), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    draw.text((14, 16), title[:90], fill=(240, 240, 240), font=get_font(30, "body"))
    for i, t in enumerate(thumbs):
        r, c = divmod(i, cols)
        sheet.paste(t, (12 + c * (cw + 12), 64 + r * (ch + 12)))
    sheet.save(dest, quality=85)
    return dest


# --------------------------------------------------------------- orquestador
def rel(path: Path) -> str:
    return path.resolve().relative_to(config.ROOT.resolve()).as_posix()


def render_item(item: dict, settings: dict | None = None) -> dict:
    """Genera los archivos de una publicación y devuelve el bloque `media` para la cola."""
    settings = settings or config.load_settings()
    out_dir = config.MEDIA_DIR / item["id"]
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    voice = item.get("voice") or settings.get("tts_voice", "es-CL-CatalinaNeural")
    rate = settings.get("tts_rate", "+0%")
    t = item["type"]

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        if not q.is_video(item):
            size = VERTICAL if t == "story" else FEED
            files = []
            for i, scene in enumerate(item["scenes"], 1):
                src, kind = fetch_visual(scene["visual"], size, work, seed_for(item["id"], i))
                if kind != "image":
                    raise RenderError("Las imágenes de feed no pueden venir de un video")
                name = "story.jpg" if t == "story" else ("post.jpg" if t == "image" else f"slide_{i:02d}.jpg")
                files.append(compose_still(src, scene, size, out_dir / name))
            preview = contact_sheet(files, out_dir / "preview.jpg", f"{item['id']} · {t}")
            return {"kind": "image" if len(files) == 1 else "carousel",
                    "files": [rel(f) for f in files], "preview": rel(preview)}

        clips, mids, elapsed = [], [], 0.0
        for i, scene in enumerate(item["scenes"], 1):
            src, kind = fetch_visual(scene["visual"], VERTICAL, work, seed_for(item["id"], i))
            overlay = work / f"overlay_{i}.png"
            overlay_for(scene, VERTICAL).save(overlay)
            audio = tts(scene.get("narration", ""), voice, rate, work / f"voice_{i}.mp3")
            if scene.get("duration") is None and kind == "video":
                dur = min(media_duration(src) or 4.0, 90.0)  # video propio: se usa completo
            else:
                dur = float(scene.get("duration", 4))
            if audio:
                dur = max(dur, media_duration(audio) + 0.35)
            clip = scene_clip(src, kind, overlay, audio, dur, work / f"clip_{i:02d}.mp4",
                              zoom_in=i % 2 == 1, keep_audio=bool(scene.get("keep_audio")))
            clips.append(clip)
            mids.append(elapsed + dur / 2)
            elapsed += dur
        music = config.ROOT / item["music"] if item.get("music") else None
        name = "story.mp4" if t == "story" else "reel.mp4"
        video = finalize_video(clips, music, float(settings.get("music_volume", 0.12)),
                               out_dir / name, work)
        if item.get("cover"):  # portada propia (material/portadas/...), ajustada a 9:16
            cimg = ImageOps.fit(ImageOps.exif_transpose(Image.open(config.ROOT / item["cover"])).convert("RGB"),
                                VERTICAL, Image.LANCZOS)
            cover = out_dir / "cover.jpg"
            cimg.save(cover, quality=92)
        else:
            cover = frame_at(video, min(1.0, elapsed / 2), out_dir / "cover.jpg")
        frames = [frame_at(video, m, work / f"mid_{k}.jpg") for k, m in enumerate(mids)]
        if item.get("cover"):
            frames.insert(0, cover)
        preview = contact_sheet(frames, out_dir / "preview.jpg",
                                f"{item['id']} · {t} · {media_duration(video):.0f}s")
        return {"kind": "video", "files": [rel(video)], "cover": rel(cover),
                "preview": rel(preview), "duration": round(media_duration(video), 1),
                "size_mb": round(video.stat().st_size / 1e6, 2)}


def describe(media: dict) -> str:
    return json.dumps(media, ensure_ascii=False)
