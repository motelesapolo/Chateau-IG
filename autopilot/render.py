"""Convierte una publicación de la cola en archivos listos para Instagram.

- Imágenes de feed: JPG 1080x1350 (4:5).
- Reels e historias de video: MP4 H.264/AAC 1080x1920, 30 fps, < 19 MB.
- Historias de imagen: JPG 1080x1920.

Todo es gratis: imágenes IA de Pollinations, stock de Pixabay/Pexels, voz de edge-tts,
y el montaje con ffmpeg + Pillow.
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
    url = f"https://image.pollinations.ai/prompt/{quote(vis['prompt'])}"
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


def _hex(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _card(vis: dict, size: tuple[int, int], dest: Path) -> Path:
    top = _hex(vis.get("bg", "#14213d"))
    bottom = _hex(vis.get("bg2", vis.get("bg", "#1f4068")))
    w, h = size
    grad = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        grad.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    grad.resize((w, h)).save(dest, quality=95)
    return dest


def fetch_visual(vis: dict, size: tuple[int, int], workdir: Path, seed: int) -> tuple[Path, str]:
    """Descarga/genera el visual. Devuelve (ruta, 'image'|'video')."""
    src = vis["source"]
    if src == "pollinations":
        return _pollinations(vis, size, workdir / f"ai_{seed}.jpg", seed), "image"
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
        return path, "video" if path.suffix.lower() in VIDEO_EXT else "image"
    raise RenderError(f"Fuente desconocida: {src}")


# ---------------------------------------------------------------------- texto
_FONT_CACHE: dict[int, ImageFont.FreeTypeFont] = {}


def font_path() -> str | None:
    custom = sorted((config.ASSETS_DIR / "fonts").glob("*.[ot]tf")) if (config.ASSETS_DIR / "fonts").is_dir() else []
    if custom:
        return str(custom[0])
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


def get_font(size: int):
    if size not in _FONT_CACHE:
        path = font_path()
        font = ImageFont.truetype(path, size) if path else ImageFont.load_default(size)
        # Fuentes variables (p. ej. Montserrat[wght].ttf): forzar un peso grueso y legible.
        try:
            names = [n.decode() if isinstance(n, bytes) else n for n in font.get_variation_names()]
            for wanted in ("ExtraBold", "Bold", "Black"):
                if wanted in names:
                    font.set_variation_by_name(wanted)
                    break
        except (OSError, AttributeError):
            pass
        _FONT_CACHE[size] = font
    return _FONT_CACHE[size]


_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
                       "‍️⭐⬆↔-⇿]+")


def clean_overlay_text(text: str) -> str:
    """Los emojis no se pueden dibujar con la tipografía del texto: se quitan (en el caption sí van)."""
    return re.sub(r"[ \t]{2,}", " ", _EMOJI_RE.sub("", text or "")).strip()


def is_light(color: str) -> bool:
    r, g, b = _hex(color)
    return (0.299 * r + 0.587 * g + 0.114 * b) > 160


def _wrap(text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words, cur = paragraph.split(), ""
        for word in words:
            trial = f"{cur} {word}".strip()
            if font.getlength(trial) <= max_width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def text_overlay(text: str, size: tuple[int, int], position: str = "center",
                 boxed: bool = True, dark_text: bool = False) -> Image.Image:
    """PNG transparente del tamaño del lienzo con el texto grande y legible."""
    w, h = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    text = clean_overlay_text(text)
    if not text:
        return layer
    max_w = int(w * 0.80)
    fsize = 96 if len(text) < 40 else 80 if len(text) < 80 else 64
    while True:
        font = get_font(fsize)
        lines = _wrap(text, font, max_w)
        if (len(lines) <= 6 and all(font.getlength(line) <= max_w for line in lines)) or fsize <= 40:
            break
        fsize -= 6
    ascent, descent = font.getmetrics()
    line_h = int((ascent + descent) * 1.12)
    block_h = line_h * len(lines)
    block_w = max(int(font.getlength(line)) for line in lines)
    centers = {"top": 0.20, "upper": 0.30, "center": 0.50, "lower": 0.72, "bottom": 0.78}
    cy = int(h * centers.get(position, 0.5))
    y0 = max(int(h * 0.10), cy - block_h // 2)
    draw = ImageDraw.Draw(layer)
    if boxed:
        pad = int(fsize * 0.45)
        draw.rounded_rectangle([(w - block_w) // 2 - pad, y0 - pad,
                                (w + block_w) // 2 + pad, y0 + block_h + pad // 2],
                               radius=pad, fill=(0, 0, 0, 150))
    for i, line in enumerate(lines):
        lw = font.getlength(line)
        if dark_text:
            draw.text(((w - lw) / 2, y0 + i * line_h), line, font=font, fill=(26, 26, 26, 255))
        else:
            draw.text(((w - lw) / 2, y0 + i * line_h), line, font=font, fill=(255, 255, 255, 255),
                      stroke_width=max(2, fsize // 24), stroke_fill=(0, 0, 0, 200))
    return layer


def overlay_for(scene: dict, size: tuple[int, int]) -> Image.Image:
    vis = scene["visual"]
    is_card = vis["source"] == "card"
    dark = is_card and is_light(vis.get("bg", "#14213d")) and is_light(vis.get("bg2", vis.get("bg", "#14213d")))
    return text_overlay(scene.get("text", ""), size, default_position(scene, size),
                        boxed=not is_card, dark_text=dark)


def default_position(scene: dict, size: tuple[int, int]) -> str:
    if scene.get("text_position"):
        return scene["text_position"]
    if scene["visual"]["source"] == "card":
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
def scene_clip(src: Path, kind: str, overlay_png: Path, audio: Path | None, duration: float,
               dest: Path, zoom_in: bool = True) -> Path:
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
    draw.text((14, 16), title[:90], fill=(240, 240, 240), font=get_font(30))
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
            dur = float(scene.get("duration", 4))
            if audio:
                dur = max(dur, media_duration(audio) + 0.35)
            clip = scene_clip(src, kind, overlay, audio, dur, work / f"clip_{i:02d}.mp4",
                              zoom_in=i % 2 == 1)
            clips.append(clip)
            mids.append(elapsed + dur / 2)
            elapsed += dur
        music = config.ROOT / item["music"] if item.get("music") else None
        name = "story.mp4" if t == "story" else "reel.mp4"
        video = finalize_video(clips, music, float(settings.get("music_volume", 0.12)),
                               out_dir / name, work)
        cover = frame_at(video, min(1.0, elapsed / 2), out_dir / "cover.jpg")
        frames = [frame_at(video, m, work / f"mid_{k}.jpg") for k, m in enumerate(mids)]
        preview = contact_sheet(frames, out_dir / "preview.jpg",
                                f"{item['id']} · {t} · {media_duration(video):.0f}s")
        return {"kind": "video", "files": [rel(video)], "cover": rel(cover),
                "preview": rel(preview), "duration": round(media_duration(video), 1),
                "size_mb": round(video.stat().st_size / 1e6, 2)}


def describe(media: dict) -> str:
    return json.dumps(media, ensure_ascii=False)
