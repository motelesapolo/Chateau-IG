"""Modelo de lenguaje gratis (Groq, compatible con la API de OpenAI) para responder la bandeja."""
from __future__ import annotations

import json
import logging
import time

import requests

log = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class LLMError(RuntimeError):
    pass


class GroqLLM:
    def __init__(self, api_key: str, models: list[str], session: requests.Session | None = None):
        self.key = api_key
        self.models = models or ["llama-3.3-70b-versatile"]
        self.http = session or requests.Session()

    def json_chat(self, system: str, user: str, temperature: float = 0.6) -> dict:
        last = None
        for model in self.models:
            for attempt in range(2):
                try:
                    resp = self.http.post(
                        GROQ_URL,
                        headers={"Authorization": f"Bearer {self.key}"},
                        json={
                            "model": model,
                            "temperature": temperature,
                            "response_format": {"type": "json_object"},
                            "messages": [{"role": "system", "content": system},
                                         {"role": "user", "content": user}],
                        },
                        timeout=60,
                    )
                    if resp.status_code == 429:
                        wait = float(resp.headers.get("retry-after", 20))
                        log.info("Groq pide esperar %.0fs (%s)", wait, model)
                        time.sleep(min(wait, 60))
                        continue
                    resp.raise_for_status()
                    content = resp.json()["choices"][0]["message"]["content"]
                    return json.loads(content)
                except (requests.RequestException, KeyError, ValueError) as exc:
                    last = exc
                    log.warning("Falló %s (intento %d): %s", model, attempt + 1, exc)
                    time.sleep(3)
        raise LLMError(f"Ningún modelo respondió: {last}")
