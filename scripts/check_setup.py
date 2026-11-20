"""Revisa que todo esté conectado. Nunca muestra los secretos.

Uso: python scripts/check_setup.py
"""
import os
import sys

import requests

import _boot
from autopilot import config
from autopilot.api import InstagramError, client_from_env
from autopilot.llm import llm_from_env


def main() -> int:
    settings = config.load_settings()
    ok = True
    lines = ["### Revisión de la configuración", ""]

    def mark(good: bool, text: str):
        nonlocal ok
        ok &= good
        lines.append(f"- {'✅' if good else '❌'} {text}")

    persona = config.load_persona()
    pend = persona.count("[COMPLETAR")
    mark(pend == 0, "config/persona.md completo" if pend == 0 else
         f"config/persona.md tiene {pend} campos [COMPLETAR]")

    token = os.environ.get("IG_ACCESS_TOKEN")
    if token:
        try:
            c = client_from_env(settings)
            me = c.me()
            mark(True, f"Instagram conectado: @{me.get('username')} (ID {c.ig_id}, "
                       f"{me.get('followers_count', 0)} seguidores)")
            try:
                lim = c.publishing_limit()
                mark(True, f"Permiso de publicación OK (usadas hoy: {lim.get('quota_usage', 0)})")
            except InstagramError as exc:
                mark(False, f"Sin permiso de publicación: {exc}")
            try:
                c.list_conversations(limit=1)
                mark(True, "Permiso de mensajes OK")
            except InstagramError as exc:
                mark(False, f"Sin acceso a mensajes: {exc}")
        except InstagramError as exc:
            mark(False, f"Token de Instagram inválido: {exc}")
    else:
        mark(False, "Falta el secreto IG_ACCESS_TOKEN")

    if os.environ.get("GROQ_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        try:
            llm = llm_from_env(settings)
            out = llm.json_chat("Responde solo con JSON.", 'Devuelve exactamente {"ok": true}')
            mark(bool(out.get("ok")), f"IA de la bandeja responde ({llm.provider})")
        except Exception as exc:  # noqa: BLE001
            mark(False, f"La IA de la bandeja no responde: {type(exc).__name__}: {str(exc)[:120]}")
    else:
        mark(False, "Falta el secreto GEMINI_API_KEY (o GROQ_API_KEY)")

    if os.environ.get("OPENAI_API_KEY"):
        try:
            r = requests.get("https://api.openai.com/v1/models", timeout=30,
                             headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
            if r.status_code == 200:
                models = sorted(m["id"] for m in r.json().get("data", []) if m["id"].startswith("gpt-image"))
                mark(bool(models), "API de ChatGPT conectada (imágenes: " + (", ".join(models) or "ninguna") + ")")
            else:
                mark(False, f"La clave de OpenAI no funciona ({r.status_code}): {r.text[:120]}")
        except requests.RequestException as exc:
            mark(False, f"No se pudo contactar a OpenAI: {exc}")
    else:
        lines.append("- ➖ Sin OPENAI_API_KEY (opcional: sin ella las imágenes IA usan el generador gratis "
                     "y las fotos solo llevan retoque local)")

    if os.environ.get("PIXABAY_KEY"):
        r = requests.get("https://pixabay.com/api/", params={"key": os.environ["PIXABAY_KEY"], "q": "cafe",
                                                              "per_page": 3}, timeout=30)
        mark(r.status_code == 200, "Pixabay OK" if r.status_code == 200 else f"Pixabay falló ({r.status_code})")
    else:
        lines.append("- ➖ Sin PIXABAY_KEY (opcional: sin ella no se usan fotos/videos de stock de Pixabay)")
    if os.environ.get("PEXELS_KEY"):
        r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": os.environ["PEXELS_KEY"]},
                         params={"query": "cafe", "per_page": 1}, timeout=30)
        mark(r.status_code == 200, "Pexels OK" if r.status_code == 200 else f"Pexels falló ({r.status_code})")
    else:
        lines.append("- ➖ Sin PEXELS_KEY (opcional)")

    _boot.step_summary("\n".join(lines) + ("\n\n**Todo listo ✅**" if ok else "\n\n**Faltan cosas ❌**"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
