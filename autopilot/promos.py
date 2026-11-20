"""Promociones semana a semana (config/promos.json).

Solo existen las promos de este archivo, y solo mientras estén vigentes (desde/hasta, ambos inclusive).
- La bandeja (comentarios y DMs) recibe las promos vigentes de hoy junto con la persona.
- El lote semanal solo puede anunciar promos vigentes en la fecha de cada publicación.
- "mencionar": "siempre" (se puede anunciar y ofrecer) | "si_preguntan" (no se publica; el bot solo la confirma
  si el cliente pregunta por ella).
"""
from __future__ import annotations

import json
from datetime import date, datetime

from . import config

FIELDS = {"titulo", "detalle", "desde", "hasta"}


def path():
    return config.CONFIG_DIR / "promos.json"


def load() -> list[dict]:
    p = path()
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("promos", [])


def validate(promos: list[dict] | None = None) -> list[str]:
    errs = []
    for i, promo in enumerate(load() if promos is None else promos, 1):
        missing = FIELDS - promo.keys()
        if missing:
            errs.append(f"promo {i}: faltan {', '.join(sorted(missing))}")
            continue
        try:
            d1, d2 = date.fromisoformat(promo["desde"]), date.fromisoformat(promo["hasta"])
            if d2 < d1:
                errs.append(f"promo {i}: 'hasta' es anterior a 'desde'")
        except ValueError:
            errs.append(f"promo {i}: fechas en formato AAAA-MM-DD")
        if promo.get("mencionar", "siempre") not in {"siempre", "si_preguntan"}:
            errs.append(f"promo {i}: mencionar debe ser 'siempre' o 'si_preguntan'")
    return errs


def active(on: date | datetime | None = None, promos: list[dict] | None = None) -> list[dict]:
    if on is None:
        on = datetime.now(config.timezone())
    if isinstance(on, datetime):
        on = on.astimezone(config.timezone()).date()
    return [p for p in (load() if promos is None else promos)
            if date.fromisoformat(p["desde"]) <= on <= date.fromisoformat(p["hasta"])]


def as_markdown(on: date | datetime | None = None, promos: list[dict] | None = None) -> str:
    current = active(on, promos)
    lines = ["## Promociones vigentes hoy (lo único que se puede ofrecer)"]
    if not current:
        lines.append("- No hay promociones vigentes. Si preguntan: \"Por ahora no tenemos promociones activas; "
                     "síguenos para enterarte de las próximas 😊\". No inventes ninguna.")
    for p in current:
        rule = " Solo confirmarla si el cliente pregunta por ella." if p.get("mencionar") == "si_preguntan" else ""
        cond = f" Condiciones: {p['condiciones']}." if p.get("condiciones") else ""
        lines.append(f"- **{p['titulo']}:** {p['detalle']}.{cond} Vigente del {p['desde']} al {p['hasta']}.{rule}")
    return "\n".join(lines)
