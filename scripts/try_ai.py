"""Prueba de la API de ChatGPT con fotos reales: genera comparaciones antes/después.

Lee pruebas/ia/pedido.json:
  {"fotos": [{"path": "material/...", "modo": "luz"}], "generar": ["prompt en inglés"]}
y deja en pruebas/ia/resultados/ una imagen por prueba + resumen.md. No publica nada.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

import _boot
from PIL import Image, ImageDraw, ImageOps

from autopilot import config, render

OUT = config.ROOT / "pruebas" / "ia" / "resultados"


def panel(images: list[tuple[str, Image.Image]], height: int = 900) -> Image.Image:
    tiles = []
    for label, im in images:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im = im.resize((int(im.width * height / im.height), height), Image.LANCZOS)
        tile = Image.new("RGB", (im.width, height + 70), (24, 24, 24))
        tile.paste(im, (0, 70))
        ImageDraw.Draw(tile).text((16, 18), label, fill=(252, 241, 225), font=render.get_font(34, "body"))
        tiles.append(tile)
    out = Image.new("RGB", (sum(t.width for t in tiles) + 12 * (len(tiles) - 1), height + 70), (0, 0, 0))
    x = 0
    for t in tiles:
        out.paste(t, (x, 0))
        x += t.width + 12
    return out


def main() -> int:
    req = json.loads((config.ROOT / "pruebas" / "ia" / "pedido.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        old.unlink()
    lines = ["# Prueba de la API de ChatGPT", ""]
    import os
    import requests
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        lines.append("- ❌ No está el secreto OPENAI_API_KEY")
    else:
        r = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
        if r.status_code == 200:
            models = sorted(m["id"] for m in r.json().get("data", []) if m["id"].startswith("gpt-image"))
            lines.append(f"- ✅ Clave válida. Modelos de imagen visibles: {', '.join(models) or 'ninguno'}")
        else:
            lines.append(f"- ❌ La clave no funciona ({r.status_code})")
        # Prueba mínima de saldo/acceso sin gastar: una edición se intenta abajo; aquí solo se informa.
    lines.append("")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for i, foto in enumerate(req.get("fotos", []), 1):
            vis = {"source": "file", "path": foto["path"], "ia_edit": foto.get("modo", "luz")}
            original = Image.open(config.ROOT / foto["path"])
            local = render.retouch(ImageOps.exif_transpose(original), "suave")
            render.last_engine = "retoque local (la IA no respondió)"
            render.last_error = ""
            t0 = time.time()
            final = Image.open(render.prepare_photo(vis, render.VERTICAL, work, i))
            secs = time.time() - t0
            name = f"{i:02d}-{Path(foto['path']).stem}.jpg"
            panel([("Original", original), ("Retoque gratis", local),
                   (f"ChatGPT ({vis['ia_edit']})", final)]).save(OUT / name, quality=85)
            lines.append(f"- `{foto['path']}` · modo **{vis['ia_edit']}** → {render.last_engine} ({secs:.0f} s) · `{name}`")
            if render.last_error:
                lines.append(f"  - Motivo: {render.last_error}")
        for d, diseno in enumerate(req.get("disenos", []), 1):
            outs = []
            for model in diseno.get("modelos", [None]):
                dest = work / f"dis{d}-{model}.jpg"
                t0 = time.time()
                try:
                    render._openai_edit([config.ROOT / x for x in diseno["imagenes"]], diseno["prompt"], dest, True,
                                        models=[model] if model else None)
                    outs.append((f"{render.last_engine} ({time.time() - t0:.0f} s)", Image.open(dest)))
                except Exception as exc:  # noqa: BLE001
                    lines.append(f"- Diseño {d} con {model}: falló ({str(exc)[:200]})")
            if outs:
                name = f"diseno-{d:02d}-{diseno.get('nombre', '')}.jpg"
                panel(outs, height=1200).save(OUT / name, quality=88)
                for label, _ in outs:
                    lines.append(f"- Diseño {d} ({diseno.get('nombre', '')}) → {label} · `{name}`")
        for j, prompt in enumerate(req.get("generar", []), 1):
            render.last_engine = ""
            dest = work / f"gen{j}.jpg"
            try:
                render.ai_image({"prompt": prompt}, render.VERTICAL, dest, j)
                name = f"gen-{j:02d}.jpg"
                panel([(render.last_engine, Image.open(dest))]).save(OUT / name, quality=85)
                lines.append(f"- Imagen generada {j} → {render.last_engine} · `{name}`")
            except Exception as exc:  # noqa: BLE001
                lines.append(f"- Imagen generada {j}: falló ({exc})")
    (OUT / "resumen.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _boot.step_summary("\n".join(lines))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
