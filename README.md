# ig-autopilot

Una cuenta de Instagram manejada por IA, **gratis** y solo con la **API oficial de Meta**.

- **Claude** (Claude Code, una vez por semana) investiga tendencias, planifica 7 días y escribe los
  guiones de reels, carruseles, imágenes e historias → `queue/`.
- **GitHub Actions** genera las imágenes (IA gratis de Pollinations o stock de Pixabay), la voz en
  español (edge-tts) y monta los videos (ffmpeg); publica cada pieza a su hora; responde comentarios
  y DMs cada hora con un modelo gratis (Groq); y genera un informe semanal con métricas.

👉 **Empieza por [SETUP.md](SETUP.md)** (guía paso a paso desde cero).

## Estructura
```
config/persona.md        Quién es la cuenta: nicho, voz, reglas de respuesta  ← complétalo
config/settings.json     Horarios, cantidades por semana, voz, límites
queue/                   Publicaciones pendientes (un JSON por publicación)
published/               Publicaciones ya hechas (con su link)
media/<id>/preview.jpg   Vista previa de cada pieza (los archivos grandes van en la rama `media`)
reports/                 Informes semanales
autopilot/               Código (API de Instagram, render, bandeja)
scripts/                 Comandos que usan los Actions
.claude/commands/        /lote-semanal: las instrucciones de Claude
.github/workflows/       Los robots (render, publicar, bandeja, informe, renovar token)
```

## Lo que este sistema NO hace (a propósito)
No da likes, no sigue cuentas, no manda mensajes a desconocidos y no usa APIs no oficiales:
eso es lo que hace que Instagram banee cuentas. Crece con contenido y respondiendo bien.

## Desarrollo
```bash
pip install -r requirements.txt pytest
python -m pytest -q
```
