"""Descarga publicaciones públicas de cuentas de referencia (Business Discovery, API oficial) para estudiar su estilo.

Lee pruebas/referencias/pedido.json: {"cuentas": ["tout.motel", ...], "cantidad": 24}
El resultado (hojas de contacto + textos) se guarda CIFRADO con pruebas/referencias/clave-publica.crt:
solo Claude puede abrirlo (el repo es público y el material es de otras cuentas). No se republica nada.
"""
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import _boot
import requests
from PIL import Image, ImageDraw

from autopilot import config, render
from autopilot.api import client_from_env

DIR = config.ROOT / "pruebas" / "referencias"
FIELDS = ("username,name,biography,followers_count,media_count,"
          "media.limit({n}){{media_type,media_url,thumbnail_url,caption,permalink,timestamp,like_count,"
          "comments_count,children{{media_type,media_url,thumbnail_url}}}}")


def thumb(url: str) -> Image.Image | None:
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        im.thumbnail((540, 675))
        return im
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    req = json.loads((DIR / "pedido.json").read_text(encoding="utf-8"))
    client = client_from_env(config.load_settings())
    n = int(req.get("cantidad", 24))
    lines = ["# Referencias", ""]
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for user in req["cuentas"]:
            try:
                data = client.request("GET", client.ig_id, params={
                    "fields": f"business_discovery.username({user}){{{FIELDS.format(n=n)}}}"})["business_discovery"]
            except Exception as exc:  # noqa: BLE001
                lines.append(f"- {user}: no se pudo leer ({str(exc)[:200]})")
                continue
            folder = work / user
            folder.mkdir()
            info = {k: data.get(k) for k in ("username", "name", "biography", "followers_count", "media_count")}
            posts = []
            for k, m in enumerate(data.get("media", {}).get("data", []), 1):
                urls = [m.get("media_url") if m.get("media_type") != "VIDEO" else m.get("thumbnail_url")]
                for c in (m.get("children") or {}).get("data", [])[1:4]:
                    urls.append(c.get("media_url") if c.get("media_type") != "VIDEO" else c.get("thumbnail_url"))
                saved = []
                for j, u in enumerate(x for x in urls if x):
                    im = thumb(u)
                    if im:
                        name = f"{k:02d}-{j}.jpg"
                        im.save(folder / name, quality=85)
                        saved.append(name)
                posts.append({**{x: m.get(x) for x in ("media_type", "caption", "timestamp", "like_count",
                                                        "comments_count", "permalink")}, "imagenes": saved})
            (folder / "datos.json").write_text(json.dumps({"cuenta": info, "posts": posts}, ensure_ascii=False,
                                                          indent=2), encoding="utf-8")
            lines.append(f"- {user}: {len(posts)} publicaciones")
        bundle = work / "referencias.tar.gz"
        with tarfile.open(bundle, "w:gz") as tar:
            for user in req["cuentas"]:
                if (work / user).exists():
                    tar.add(work / user, arcname=user)
        out = DIR / "referencias.enc"
        subprocess.run(["openssl", "cms", "-encrypt", "-binary", "-aes256", "-outform", "DER", "-in", str(bundle),
                        "-out", str(out), str(DIR / "clave-publica.crt")], check=True)
    (DIR / "resumen.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _boot.step_summary("\n".join(lines))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
