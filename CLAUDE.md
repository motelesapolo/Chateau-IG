# ig-autopilot — instrucciones para Claude

Este repo maneja una cuenta de Instagram de forma autónoma usando **solo la API oficial de Meta**
(Instagram API with Unified Login: `graph.facebook.com`, token de usuario del sistema que no vence).
Claude crea el contenido una vez por semana; GitHub Actions hace el resto.

## Cómo funciona
| Pieza | Quién | Cuándo |
|---|---|---|
| Planificar y escribir la semana (`queue/*.json`) | Claude, con `/lote-semanal` | Domingo |
| Incorporar la cola + renderizar imágenes/videos | Action `render.yml` | Al subir una rama `claude/**` |
| Publicar a la hora indicada | Action `publish.yml` | Cada 15 min |
| Responder comentarios y DMs (Gemini o Groq; textos anonimizados) | Action `inbox.yml` | Cada hora |
| Informe con métricas (`reports/`) | Action `report.yml` | Domingo 18:00 Chile |
| Revisar que todo siga conectado (avisa por correo si falla) | Action `check.yml` | Lunes |
| Preparar fotos/videos que sube el dueño a `material/` (HEIC→JPG, sin GPS) | Action `material.yml` | Al subir material |

- El formato de cada publicación está documentado arriba de `autopilot/queue.py`. Léelo antes de escribir la cola.
- Fotos y videos reales del hotel: `material/` (ver `material/README.md`). Inventario: `python scripts/material.py inventario`.
- Estrategia de crecimiento (formatos, horarios, SEO, CTA): `config/estrategia.md`.
- Identidad, voz y reglas de la cuenta: `config/persona.md`. Ajustes: `config/settings.json`.
- Los archivos pesados viven en la rama `media` (se reescribe sola). En `main` solo queda `media/<id>/preview.jpg`.

## Reglas que no se rompen
1. **Nunca** uses APIs no oficiales, bots de navegador, ni automatices likes, follows o DMs a desconocidos.
   La bandeja solo **responde** a quien escribió primero.
2. **Nunca** guardes en el repo (ni imprimas en logs) el texto de comentarios o mensajes privados: el repo es público.
3. **Nunca** escribas secretos (tokens, claves) en archivos. Viven en GitHub → Settings → Secrets.
4. Sube tu trabajo a una rama `claude/lote-AAAA-MM-DD`; el Action la incorpora a `main` solo.
   No hace falta (ni conviene) empujar directo a `main`.
5. No edites `published/` ni publicaciones con status `rendered` salvo para corregir un error grave
   (en ese caso agrega `"replace": true`).
6. Para mostrar las habitaciones o el hotel usa SOLO material real de `material/`, nunca IA ni stock.
7. Contenido: nada de personas reales identificables, logos o personajes con derechos de autor,
   consejos médicos/financieros como si fueran de un profesional, ni datos inventados presentados como hechos.
   Si la persona de la cuenta es un personaje generado por IA, nunca lo presentes como humano real.

## Comandos útiles
```bash
python scripts/validate_queue.py            # revisa la cola
python scripts/when.py --week 2026-11-24    # horarios con la zona horaria correcta
python -m pytest -q                         # tests
DISABLE_TTS=1 python scripts/render_queue.py --no-sync <id>   # render local de prueba (necesita internet para imágenes IA)
```
