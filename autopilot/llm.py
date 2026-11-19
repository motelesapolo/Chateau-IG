"""Modelo de lenguaje para responder la bandeja.

Proveedores (APIs compatibles con OpenAI), se usa el primero cuya clave exista:
  - GROQ_API_KEY   → Groq (gratis, no entrena con tus datos)
  - GEMINI_API_KEY → Google Gemini. En el plan GRATIS, Google puede usar los textos para mejorar
                     sus productos (con revisores humanos). Por eso la bandeja anonimiza todo antes
                     de enviarlo (ver autopilot/inbox.py: redact). Con facturación activada no se usan.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time

import requests

log = logging.getLogger(__name__)

PROVIDERS = {
    "groq": {
        "env": "GROQ_API_KEY",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "settings_key": "groq_models",
        "default_models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
    },
    "gemini": {
        "env": "GEMINI_API_KEY",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "settings_key": "gemini_models",
        "default_models": ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"],
    },
}


class LLMError(RuntimeError):
    pass


def parse_json(text: str) -> dict:
    """Acepta JSON puro o envuelto en ```json ... ``` / texto alrededor."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        return json.loads(match.group(0))
    raise ValueError("La respuesta del modelo no trae JSON")


class ChatLLM:
    def __init__(self, provider: str, api_key: str, models: list[str], session: requests.Session | None = None,
                 sleep=time.sleep):
        cfg = PROVIDERS[provider]
        self.provider = provider
        self.url = cfg["url"]
        self.key = api_key
        self.models = models or cfg["default_models"]
        self.http = session or requests.Session()
        self.sleep = sleep
        self._json_mode = True  # se apaga solo si el proveedor no acepta response_format

    def _post(self, model: str, system: str, user: str, temperature: float):
        body = {"model": model, "temperature": temperature,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if self._json_mode:
            body["response_format"] = {"type": "json_object"}
        return self.http.post(self.url, headers={"Authorization": f"Bearer {self.key}"}, json=body, timeout=60)

    def json_chat(self, system: str, user: str, temperature: float = 0.6) -> dict:
        last: Exception | None = None
        for model in self.models:
            for attempt in range(3):
                try:
                    resp = self._post(model, system, user, temperature)
                    if resp.status_code == 400 and self._json_mode and "response_format" in resp.text:
                        self._json_mode = False
                        continue
                    if resp.status_code == 429:
                        wait = float(resp.headers.get("retry-after", 20 * (attempt + 1)))
                        log.info("%s pide esperar %.0fs (%s)", self.provider, wait, model)
                        self.sleep(min(wait, 60))
                        continue
                    if resp.status_code == 404:
                        raise LLMError(f"modelo {model} no disponible")
                    resp.raise_for_status()
                    content = resp.json()["choices"][0]["message"]["content"]
                    return parse_json(content)
                except LLMError as exc:
                    last = exc
                    break  # siguiente modelo
                except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
                    last = exc
                    log.warning("Falló %s/%s (intento %d): %s", self.provider, model, attempt + 1,
                                type(exc).__name__)
                    self.sleep(3)
        raise LLMError(f"Ningún modelo respondió: {type(last).__name__ if last else 'sin detalle'}")


def llm_from_env(settings: dict) -> ChatLLM:
    for name, cfg in PROVIDERS.items():
        key = os.environ.get(cfg["env"])
        if key:
            return ChatLLM(name, key, settings.get(cfg["settings_key"], []))
    raise SystemExit("Falta una clave de IA: agrega el secreto GEMINI_API_KEY (o GROQ_API_KEY) en GitHub → "
                     "Settings → Secrets and variables → Actions (ver SETUP.md).")


# Compatibilidad con código anterior
def GroqLLM(api_key: str, models: list[str], session=None) -> ChatLLM:  # noqa: N802
    return ChatLLM("groq", api_key, models, session=session)
