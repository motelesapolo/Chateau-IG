---
description: Planifica, escribe y sube el contenido de Instagram de la próxima semana
---

Eres quien maneja esta cuenta de Instagram. Prepara el lote de contenido de la **próxima semana
(lunes a domingo)** siguiendo estos pasos en orden. Trabaja solo; no hagas preguntas salvo que el
paso 1 falle. Al final deja un resumen corto.

## 1. Revisar que se puede trabajar
- Lee `CLAUDE.md`, `config/persona.md`, `config/settings.json` y la cabecera de `autopilot/queue.py`.
- Si `config/persona.md` todavía tiene `[COMPLETAR`, **detente** y explica qué falta completar.
- `git fetch origin main && git checkout -B trabajo origin/main` para partir de lo último.

## 2. Aprender de la semana anterior
- Lee el informe más reciente en `reports/` y las publicaciones de `published/` de los últimos 14 días.
- Anota qué funcionó (más alcance, guardados, compartidos) y qué no. Repite formatos ganadores,
  descarta los flojos. Si hay publicaciones con error en `queue/` (`render_failed`, `publish_failed`,
  `missed`), entiende el motivo para no repetirlo.
- Revisa qué hay todavía pendiente en `queue/` para no duplicar fechas ni temas.

## 3. Revisar el material propio del hotel
- `python scripts/material.py inventario` lista las fotos y videos reales que subió el dueño en `material/`,
  con cuántas veces se usó cada uno.
- **Mira** (con la herramienta de lectura de imágenes) cada foto que pienses usar, para describirla con exactitud.
  Para videos, extrae un fotograma: `ffmpeg -v error -ss 1 -i <video> -frames:v 1 /tmp/f.jpg` y míralo.
- Prioriza el material con menos usos y no repitas el mismo archivo dos veces en la misma semana.
- **Todo lo que muestre las habitaciones o el hotel debe salir de `material/`** (`"source": "file"`).
  Si falta material de algún tipo de habitación, no lo muestres: usa IA/stock solo para ambientar
  (café, sábanas genéricas, lluvia en la ventana, ciudad de noche) y anota en el resumen final qué material conviene subir.

## 4. Investigar (3 a 5 búsquedas web)
- Tendencias y preguntas frecuentes del nicho esta semana, fechas especiales en Chile/Latinoamérica
  en esos 7 días, y 1–2 cuentas referentes del nicho (solo para inspirarte en formatos, nunca copiar).

## 5. Planificar
- Usa las cantidades de `weekly_plan` en `config/settings.json` (reels, carruseles, imágenes, historias).
- Obtén los horarios con `python scripts/when.py --week <AAAA-MM-DD del lunes>` (zona horaria correcta).
- Reparte los pilares de contenido de la persona. Cada publicación con un objetivo claro
  (alcance, guardados, comentarios o seguidores).

## 6. Escribir la cola (`queue/<id>.json`, un archivo por publicación)
Reglas de calidad:
- **Reels (15–35 s, 4–8 escenas):** la escena 1 es el gancho (texto en pantalla de máx. 7 palabras y
  narración que genere curiosidad en <2 s). Una idea por escena. Cierre con llamado a la acción
  (comentar, guardar o seguir). `narration` en español natural, frases cortas.
- **Carruseles (5–8 láminas):** lámina 1 = promesa clara; láminas de texto con `"source": "card"`
  (colores de marca consistentes en `bg`/`bg2`); última lámina = resumen o llamado a la acción.
- **Imágenes:** una idea fuerte, texto corto encima o ninguno.
- **Historias (1 diaria):** avisos del post del día, preguntas, detrás de escena. Imagen con texto corto.
- **Visuales:**
  - `pollinations`: escribe el `prompt` en **inglés**, detallado (sujeto, estilo, luz, encuadre vertical),
    y mantén un estilo coherente toda la semana. Nada de personas reales, logos, marcas ni personajes
    con derechos de autor.
  - `pixabay_video` / `pixabay_photo` (si existe la clave): `query` corto en inglés.
  - `card`: para frases y listas.
  - `file` con `"path": "material/..."`: fotos y videos reales del hotel (obligatorio para mostrar habitaciones).
- **Caption:** primera línea = gancho; 2–5 líneas de valor; llamado a la acción; 3–8 hashtags relevantes al final.
- No inventes datos: si das cifras o consejos, que vengan de lo que investigaste en el paso 3.
- `id` = `AAAA-MM-DD-tipo-tema` (minúsculas y guiones). `status` = `"planned"`.

Luego ejecuta `python scripts/validate_queue.py` y corrige hasta que todo esté ✅.

## 7. Subir
```bash
git checkout -b claude/lote-<AAAA-MM-DD del lunes>
git add queue && git commit -m "Lote semanal <fecha>" && git push -u origin HEAD
```
El Action **1 · Renderizar contenido** incorpora la cola a `main`, genera imágenes/videos y borra la rama.

## 8. Revisar el resultado (control de calidad)
- Espera a que termine el render: cada 60 s ejecuta `git fetch origin main` y revisa con
  `git show origin/main:queue/<id>.json` si el `status` cambió a `rendered` o `render_failed`
  (máximo ~30 minutos).
- `git checkout -B trabajo origin/main` y **mira** cada `media/<id>/preview.jpg` con la herramienta de
  lectura de imágenes. Revisa: texto legible y sin errores, imágenes coherentes, sin deformaciones
  feas, sin texto basura generado por la IA dentro de la imagen.
- Si algo falla: corrige el JSON (prompt, texto, fuente), agrega `"replace": true`, y súbelo en una rama
  nueva `claude/fix-<fecha>` (máximo 2 rondas de corrección). Si es `render_failed`, lee el campo
  `error` y corrige la causa.

## 9. Resumen final
Escribe un resumen breve: qué se programó (fecha, tipo, tema), qué aprendiste del informe y
cualquier cosa que el dueño de la cuenta deba revisar en la app (mensajes marcados para revisión).
