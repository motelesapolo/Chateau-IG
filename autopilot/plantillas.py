"""Plantillas de la línea editorial (config/linea-editorial.md), dibujadas con HTML + Chrome.

Formatos: foto-frase · detalle · serie · chat · grafica · cierre.
Texto: la palabra entre *asteriscos* va destacada (Playfair Italic dorada). La IA nunca escribe texto.
"""
from __future__ import annotations

import html
import os
import re
import shutil
from pathlib import Path

from . import config

FEED = (1080, 1350)
VERTICAL = (1080, 1920)
FORMATOS = {"foto-frase", "detalle", "serie", "chat", "grafica", "cierre"}
FONDOS_SERIE = {"rojo": ("#811721", "#FCF1E1", "#C9A063", "logo_crema.png"),
                "vino": ("#5E0F17", "#FCF1E1", "#C9A063", "logo_crema.png"),
                "arena": ("#F5DFC5", "#811721", "#9C6A2B", "logo_rojo.png")}


def _rich(text: str) -> str:
    """Escapa el texto y convierte *palabra* en <em>palabra</em>; '\\n' en salto de línea."""
    out = html.escape(text or "")
    out = re.sub(r"\*(.+?)\*", r"<em>\1</em>", out)
    return out.replace("\n", "<br>")


def _assets() -> dict:
    root = config.ROOT
    return {"fonts": (root / "assets" / "fonts").as_uri(), "brand": (root / "assets" / "brand").as_uri()}


def _ensure_logos() -> None:
    """logo_rojo.png (para fondos claros) se genera desde logo_crema.png si falta."""
    brand = config.ROOT / "assets" / "brand"
    rojo = brand / "logo_rojo.png"
    if not rojo.exists() and (brand / "logo_crema.png").exists():
        from PIL import Image
        l = Image.open(brand / "logo_crema.png").convert("RGBA")
        r = Image.new("RGBA", l.size, (129, 23, 33, 255))
        r.putalpha(l.getchannel("A"))
        r.save(rojo)


BASE_CSS = """
@font-face { font-family: Play; src: url("{fonts}/PlayfairDisplay[wght].ttf"); font-weight: 400 900; }
@font-face { font-family: Play; src: url("{fonts}/PlayfairDisplay-Italic[wght].ttf"); font-weight: 400 900; font-style: italic; }
@font-face { font-family: Man; src: url("{fonts}/Manrope[wght].ttf"); font-weight: 200 800; }
:root { --rojo:#811721; --vino:#5E0F17; --crema:#FCF1E1; --beige:#F3D8B9; --arena:#F5DFC5; --dorado:#9C6A2B; --oro:#C9A063; --cafe:#2A1C14; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: {w}px; height: {h}px; overflow: hidden; }
body { font-family: Man, sans-serif; position: relative; -webkit-font-smoothing: antialiased; }
.grain::after { content:""; position:absolute; inset:0; pointer-events:none; opacity:.14; mix-blend-mode:multiply;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.35  0 0 0 0 0.25  0 0 0 0 0.15  0 0 0 .55 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>"); }
.t { font-family: Play, serif; font-weight: 500; line-height: 1.04; letter-spacing: -.01em; }
.t em { font-style: italic; font-weight: 500; color: var(--oro); }
.k { font-weight: 800; letter-spacing: .32em; text-transform: uppercase; font-size: 24px; }
.s { font-weight: 600; font-size: 34px; line-height: 1.3; }
.bg { position:absolute; inset:0; } .bg img { width:100%; height:100%; object-fit:cover; }
.logo { position:absolute; left:0; right:0; text-align:center; } .logo img { width: 150px; }
"""

FIT_JS = """
for (const el of document.querySelectorAll('[data-fit]')) {
  const max = parseFloat(el.dataset.fit); let size = parseFloat(getComputedStyle(el).fontSize);
  while (el.scrollHeight > max && size > 40) { size -= 3; el.style.fontSize = size + 'px'; }
}
"""


def _page(size: tuple[int, int], body: str, extra_css: str = "", grain: bool = True) -> str:
    a = _assets()
    css = BASE_CSS.replace("{fonts}", a["fonts"]).replace("{w}", str(size[0])).replace("{h}", str(size[1]))
    return (f"<html><head><meta charset='utf-8'><style>{css}{extra_css}</style></head>"
            f"<body class='{'grain' if grain else ''}'>{body}<script>{FIT_JS}</script></body></html>")


def html_for(formato: str, size: tuple[int, int], data: dict) -> str:
    """data: kicker, text, subtext, cta, photo (ruta), fondo (ruta), bg, mensajes, logo."""
    a = _assets()
    w, h = size
    vertical = h > w * 1.5
    top_safe, bottom_safe = (270, 340) if vertical else (60, 70)
    kicker, text, sub = data.get("kicker", ""), _rich(data.get("text", "")), _rich(data.get("subtext", ""))
    if formato in {"foto-frase", "detalle"}:
        photo = Path(data["photo"]).as_uri()
        pos = data.get("posicion", "50% 50%")
        size_t = (150 if formato == "detalle" else 118) * (1.1 if vertical else 1)
        logo = (f"<div class='logo' style='top:{top_safe - 10 if vertical else 52}px'><img src='{a['brand']}/logo_crema.png'></div>"
                if formato == "foto-frase" and data.get("logo", True) else "")
        body = f"""<div class='bg'><img src='{photo}' style='object-position:{pos}'></div>
<div style='position:absolute;inset:0;background:linear-gradient(180deg,rgba(40,6,10,.55) 0%,rgba(40,6,10,0) 22%,rgba(40,6,10,0) 42%,rgba(40,6,10,.93) 100%)'></div>
{logo}
<div style='position:absolute;left:72px;right:72px;bottom:{bottom_safe + 40}px;color:var(--crema)'>
{f"<div class='k' style='color:var(--oro);margin-bottom:22px'>{html.escape(kicker)}</div>" if kicker else ""}
<div class='t' data-fit='{int(h * .36)}' style='font-size:{size_t:.0f}px'>{text}</div>
{f"<div class='s' style='margin-top:26px'>{sub}</div>" if sub else ""}</div>"""
        return _page(size, body)
    if formato == "serie":
        bg, fg, accent, logo = FONDOS_SERIE.get(data.get("bg", "rojo"), FONDOS_SERIE["rojo"])
        cta = data.get("cta", "Desliza →")
        body = f"""<div style='position:absolute;inset:0;background:{bg};color:{fg}'></div>
<div style='position:absolute;left:90px;right:90px;top:{top_safe}px;bottom:{bottom_safe}px;display:flex;flex-direction:column;justify-content:center;color:{fg}'>
{f"<div class='k' style='color:{accent}'>{html.escape(kicker)}</div>" if kicker else ""}
<div class='t' data-fit='{int(h * .45)}' style='font-size:{140 if vertical else 128}px;margin:30px 0 34px'>{text}</div>
<div style='width:120px;height:3px;background:{accent};margin-bottom:30px'></div>
{f"<div class='s' style='opacity:.92'>{sub}</div>" if sub else ""}</div>
<div style='position:absolute;left:90px;bottom:{bottom_safe - 50 if vertical else 52}px'><img src='{a['brand']}/{logo}' style='width:110px'></div>
{f"<div style='position:absolute;right:90px;bottom:{bottom_safe - 30 if vertical else 66}px;font-weight:800;letter-spacing:.2em;font-size:22px;color:{accent};text-transform:uppercase'>{html.escape(cta)}</div>" if cta else ""}"""
        css = f".t em {{ color: {accent}; }}"
        return _page(size, body, css)
    if formato == "chat":
        msgs = "".join(
            f"<div class='m {'b' if m.get('de') == 'b' else 'a'}'>{html.escape(m['texto'])}"
            f"<span class='tm'>{html.escape(m.get('hora', ''))}</span></div>" for m in data.get("mensajes", []))
        cta = data.get("cta", "Desliza →")
        body = f"""<div style='position:absolute;inset:0;background:var(--vino)'></div>
<div class='k' style='position:absolute;top:{top_safe + 10 if vertical else 80}px;left:110px;color:var(--oro)'>{html.escape(kicker)}</div>
<div style='position:absolute;left:0;right:0;top:{top_safe + 70 if vertical else 150}px;bottom:{bottom_safe - 20 if vertical else 170}px;display:flex;align-items:center'>
<div class='ph'>
<div class='hd'><div class='av'><img src='{a['brand']}/logo_crema.png'></div><div><div style='font-weight:800;font-size:29px'>{html.escape(data.get('contacto', 'Amor'))}</div><div style='font-size:19px;opacity:.65'>en línea</div></div></div>
<div class='ms'>{msgs}</div></div></div>
<div style='position:absolute;left:110px;bottom:{bottom_safe - 110 if vertical else 50}px'><img src='{a['brand']}/logo_crema.png' style='width:100px'></div>
{f"<div style='position:absolute;bottom:{bottom_safe - 100 if vertical else 62}px;right:110px;font-weight:800;letter-spacing:.2em;font-size:22px;color:var(--oro);text-transform:uppercase'>{html.escape(cta)}</div>" if cta else ""}"""
        css = """.ph{position:relative;margin:0 110px;flex:1;border-radius:44px;background:#1d090c;border:2px solid rgba(201,160,99,.55);box-shadow:0 30px 70px rgba(0,0,0,.5);overflow:hidden;color:var(--crema)}
.hd{display:flex;align-items:center;gap:20px;padding:28px 32px;background:#3b0b12} .av{width:66px;height:66px;border-radius:50%;background:var(--rojo);border:2px solid var(--oro);display:flex;align-items:center;justify-content:center} .av img{width:48px}
.ms{padding:38px 32px;display:flex;flex-direction:column;gap:24px} .m{max-width:80%;padding:20px 26px;border-radius:24px;font-size:31px;font-weight:600;line-height:1.3}
.a{align-self:flex-start;background:#3a1218;border:1px solid rgba(201,160,99,.3);border-bottom-left-radius:6px} .b{align-self:flex-end;background:var(--beige);color:var(--cafe);border-bottom-right-radius:6px}
.tm{display:block;font-size:17px;opacity:.5;text-align:right;margin-top:4px}"""
        return _page(size, body, css)
    if formato == "grafica":
        fondo = Path(data["fondo"]).as_uri() if data.get("fondo") else ""
        bgimg = f"<div class='bg'><img src='{fondo}' style='object-position:50% 70%'></div>" if fondo else \
            "<div class='bg' style='background:radial-gradient(90% 60% at 50% 40%,#8d1f2a,var(--vino))'></div>"
        body = f"""{bgimg}
<div style='position:absolute;inset:0;background:linear-gradient(180deg,rgba(40,6,10,.78) 0%,rgba(40,6,10,.25) 55%,rgba(40,6,10,0) 100%)'></div>
<div class='logo' style='top:{top_safe - 10 if vertical else 52}px'><img src='{a['brand']}/logo_crema.png'></div>
<div style='position:absolute;left:80px;right:80px;top:{top_safe + 170 if vertical else 240}px;color:var(--crema);text-align:center'>
{f"<div class='k' style='color:var(--oro)'>{html.escape(kicker)}</div>" if kicker else ""}
<div class='t' data-fit='{int(h * .34)}' style='font-size:{150 if vertical else 132}px;margin:28px 0'>{text}</div>
{f"<div class='s'>{sub}</div>" if sub else ""}</div>"""
        return _page(size, body)
    if formato == "cierre":
        body = f"""<div style='position:absolute;inset:0;background:radial-gradient(80% 60% at 50% 45%,#8d1f2a,var(--rojo) 55%,var(--vino))'></div>
<div style='position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--crema);text-align:center'>
<img src='{a['brand']}/logo_crema.png' style='width:{380 if vertical else 340}px'>
<div style='width:120px;height:3px;background:var(--oro);margin:46px 0 34px'></div>
<div class='t' style='font-size:64px'>{_rich(data.get('text') or 'Reserva por *WhatsApp*')}</div>
<div class='s' style='margin-top:18px;opacity:.85'>{sub or 'Link en el perfil'}</div></div>"""
        return _page(size, body)
    raise ValueError(f"Formato desconocido: {formato}")


def chrome_path() -> str | None:
    for c in (os.environ.get("CHROME_PATH"), shutil.which("google-chrome"), shutil.which("chromium"),
              shutil.which("chromium-browser"), "/usr/bin/google-chrome"):
        if c and Path(c).exists():
            return c
    return None


def render(formato: str, size: tuple[int, int], data: dict, dest: Path) -> Path:
    """Dibuja la plantilla y guarda un JPG del tamaño exacto."""
    from playwright.sync_api import sync_playwright
    from PIL import Image
    _ensure_logos()
    page_file = dest.with_suffix(".html")
    page_file.write_text(html_for(formato, size, data), encoding="utf-8")
    png = dest.with_suffix(".png")
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chrome_path(), args=["--allow-file-access-from-files"])
        page = browser.new_page(viewport={"width": size[0], "height": size[1]})
        page.goto(page_file.as_uri())
        page.wait_for_timeout(500)
        page.screenshot(path=str(png))
        browser.close()
    Image.open(png).convert("RGB").save(dest, quality=95)
    return dest
