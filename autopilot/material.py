"""Material propio del hotel (fotos y videos reales) en material/.

- optimize(): deja cada archivo listo para usar y seguro para un repo público:
  fotos → JPG (HEIC/PNG/WebP incluidos), máx. 2160 px, sin metadatos (GPS, modelo del celular…);
  videos → MP4 H.264, máx. 1080 px en el lado corto, sin metadatos ni pistas extra.
- inventory(): lista el material con cuántas veces se ha usado, para que el lote semanal
  priorice lo menos visto.
"""
from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from pathlib import Path

from PIL import Image, ImageOps

from . import config

log = logging.getLogger(__name__)

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".3gp", ".webm"}
MAX_IMAGE_SIDE = 2160
REGISTRY = ".procesados.json"


def material_dir() -> Path:
    return config.ROOT / "material"


def _sha(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _registry() -> dict:
    p = material_dir() / REGISTRY
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def _save_registry(data: dict) -> None:
    (material_dir() / REGISTRY).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")


def _free_name(path: Path) -> Path:
    if not path.exists():
        return path
    for i in range(2, 1000):
        cand = path.with_name(f"{path.stem}-{i}{path.suffix}")
        if not cand.exists():
            return cand
    raise RuntimeError(f"Demasiados archivos con el nombre {path.name}")


def _clean_stem(name: str) -> str:
    keep = "".join(c.lower() if c.isalnum() else "-" for c in name)
    while "--" in keep:
        keep = keep.replace("--", "-")
    return keep.strip("-") or "archivo"


def optimize_image(src: Path) -> Path:
    try:
        import pillow_heif  # noqa: F401
        pillow_heif.register_heif_opener()
    except ImportError:
        if src.suffix.lower() in {".heic", ".heif"}:
            raise
    img = Image.open(src)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.LANCZOS)
    dest = src.with_name(_clean_stem(src.stem) + ".jpg")
    tmp = src.with_name(".tmp-" + dest.name)
    img.save(tmp, "JPEG", quality=88, optimize=True)  # sin exif= → sin metadatos
    if src != dest:
        src.unlink()
        dest = _free_name(dest)
    tmp.replace(dest)
    return dest


def optimize_video(src: Path) -> Path:
    dest = src.with_name(_clean_stem(src.stem) + ".mp4")
    tmp = src.with_name(".tmp-" + dest.name)
    # Lado corto a máx. 1080 px, respetando orientación; sin metadatos ni pistas extra.
    vf = "scale='if(gt(iw,ih),-2,min(1080,iw))':'if(gt(iw,ih),min(1080,ih),-2)',fps=30,format=yuv420p"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
           "-map", "0:v:0", "-map", "0:a:0?", "-map_metadata", "-1", "-map_chapters", "-1",
           "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(tmp)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"No se pudo procesar el video {src.name}: {proc.stderr[-400:]}")
    if src != dest:
        src.unlink()
        dest = _free_name(dest)
    tmp.replace(dest)
    return dest


def optimize() -> dict:
    """Procesa lo nuevo o cambiado. Devuelve {"ok": [...], "errores": [...]}."""
    root = material_dir()
    reg = _registry()
    out = {"ok": [], "errores": []}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.startswith(".") or path.name.lower() == "readme.md":
            continue
        ext = path.suffix.lower()
        rel = path.relative_to(config.ROOT).as_posix()
        if ext not in IMAGE_EXT | VIDEO_EXT:
            out["errores"].append(f"{rel}: tipo de archivo no soportado")
            continue
        if reg.get(rel) == _sha(path):
            continue
        try:
            dest = optimize_image(path) if ext in IMAGE_EXT else optimize_video(path)
            drel = dest.relative_to(config.ROOT).as_posix()
            reg.pop(rel, None)
            reg[drel] = _sha(dest)
            out["ok"].append(drel)
        except Exception as exc:  # noqa: BLE001
            out["errores"].append(f"{rel}: {exc}")
    # Olvidar archivos borrados
    for rel in list(reg):
        if not (config.ROOT / rel).exists():
            reg.pop(rel)
    _save_registry(reg)
    return out


def _usage() -> dict[str, list[str]]:
    used: dict[str, list[str]] = {}
    for d in (config.QUEUE_DIR, config.PUBLISHED_DIR):
        for p in d.glob("*.json"):
            try:
                item = json.loads(p.read_text())
            except ValueError:
                continue
            for scene in item.get("scenes", []):
                vis = scene.get("visual") or {}
                if vis.get("source") == "file" and str(vis.get("path", "")).startswith("material/"):
                    used.setdefault(vis["path"], []).append(item.get("id", p.stem))
    return used


def inventory() -> list[dict]:
    used = _usage()
    rows = []
    for path in sorted(material_dir().rglob("*")):
        if not path.is_file() or path.name.startswith(".") or path.name.lower() == "readme.md":
            continue
        rel = path.relative_to(config.ROOT).as_posix()
        kind = "video" if path.suffix.lower() in VIDEO_EXT else "foto"
        info = {"path": rel, "tipo": kind, "categoria": "/".join(path.parent.relative_to(material_dir()).parts),
                "usos": len(used.get(rel, [])), "usado_en": used.get(rel, [])[-3:]}
        if kind == "foto":
            try:
                with Image.open(path) as im:
                    info["tamano"] = f"{im.width}x{im.height}"
                    info["orientacion"] = "vertical" if im.height > im.width else "horizontal"
            except OSError:
                pass
        else:
            probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                    "stream=width,height:format=duration", "-of", "json", str(path)],
                                   capture_output=True, text=True)
            try:
                data = json.loads(probe.stdout)
                st = data["streams"][0]
                info["tamano"] = f"{st['width']}x{st['height']}"
                info["orientacion"] = "vertical" if st["height"] > st["width"] else "horizontal"
                info["segundos"] = round(float(data["format"]["duration"]), 1)
            except (ValueError, KeyError, IndexError):
                pass
        rows.append(info)
    rows.sort(key=lambda r: (r["categoria"], r["usos"], r["path"]))
    return rows
