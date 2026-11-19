"""Responde comentarios y DMs nuevos. Corre cada hora en GitHub Actions.

Uso: python scripts/inbox.py        (DRY_RUN=1 para decidir sin enviar nada)
"""
import sys

import _boot
from autopilot import config
from autopilot.api import client_from_env
from autopilot.inbox import Inbox, State
from autopilot.llm import GroqLLM


def main() -> int:
    settings = config.load_settings()
    persona = config.load_persona()
    if "[COMPLETAR" in persona:
        print("config/persona.md tiene campos [COMPLETAR]; la bandeja no responde hasta completarlos.")
        return 0
    client = client_from_env(settings)
    llm = GroqLLM(config.env("GROQ_API_KEY"), settings.get("groq_models", []))
    state = State(config.STATE_DIR / "inbox.json")
    stats = Inbox(client, llm, persona, settings, state, dry_run=config.dry_run()).run()
    _boot.step_summary("### Bandeja\n" + stats.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
