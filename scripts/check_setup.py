"""Revisa que todo esté conectado. Nunca muestra los secretos.

Uso: python scripts/check_setup.py
"""
import os
import sys

import requests

import _boot
from autopilot import config
from autopilot.api import InstagramClient, InstagramError
from autopilot.llm import GroqLLM


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
            c = InstagramClient(token, settings.get("api_version", "v25.0"))
            me = c.me()
            mark(True, f"Instagram conectado: @{me.get('username')} ({me.get('account_type')})")
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

    if os.environ.get("GROQ_API_KEY"):
        try:
            GroqLLM(os.environ["GROQ_API_KEY"], settings.get("groq_models", [])).json_chat(
                "Responde en JSON.", 'Devuelve {"ok": true}')
            mark(True, "Groq responde")
        except Exception as exc:  # noqa: BLE001
            mark(False, f"Groq no responde: {type(exc).__name__}")
    else:
        mark(False, "Falta el secreto GROQ_API_KEY")

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
    if os.environ.get("GITHUB_ACTIONS"):
        mark(bool(os.environ.get("HAS_GH_PAT")), "GH_PAT configurado (para renovar el token solo)"
             if os.environ.get("HAS_GH_PAT") else "Falta GH_PAT: el token de Instagram no se renovará solo")

    _boot.step_summary("\n".join(lines) + ("\n\n**Todo listo ✅**" if ok else "\n\n**Faltan cosas ❌**"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
