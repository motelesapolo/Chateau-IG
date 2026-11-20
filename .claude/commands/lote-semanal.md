---
description: Planifica, escribe y sube el contenido de Instagram de la próxima semana
---

Eres quien maneja esta cuenta de Instagram. Prepara el lote de contenido de la **próxima semana
(desde el lunes 18:00 hasta el domingo)**. El lunes hasta las 13:30 el dueño revisa todo en un issue de GitHub
y puede desmarcar o pedir cambios (los aplica `/revision-lunes`). Sigue siguiendo estos pasos en orden. Trabaja solo; no hagas preguntas salvo que el
paso 1 falle. Al final deja un resumen corto.

## 1. Revisar que se puede trabajar
- Lee `CLAUDE.md`, `config/persona.md`, **`config/marca.md`** (paleta, tipografías, logo), **`config/estrategia.md`** (cómo crecer: formatos, horarios, SEO, CTA),
  `config/settings.json` y la cabecera de `autopilot/queue.py`.
- Si `config/persona.md` todavía tiene `[COMPLETAR`, **detente** y explica qué falta completar.
- **Promos:** lee `config/promos.json`. Luego revisa los comentarios del dueño (author_association OWNER, MEMBER o
  COLLABORATOR) en los issues de revisión abiertos
  (`curl -s "https://api.github.com/repos/<owner>/<repo>/issues?labels=revision&state=open"` y luego
  `/issues/<n>/comments`) que hablen de una **promo nueva** para la próxima semana. Agrégala a `config/promos.json`
  con título, detalle, condiciones, `desde`/`hasta` y `mencionar` (si falta un dato esencial como precio o fechas,
  no la inventes: anótalo en el resumen y no la publiques). Ese archivo va en la misma rama del lote.
  **Solo se anuncian promos vigentes en la fecha de cada publicación. Si no hay ninguna, no se habla de promos.**
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
  **Por ahora solo imágenes: nada de reels ni historias en video** (`reel: 0`). Todo es `image`, `carousel` o
  `story` con imagen fija.
- **El lunes no se publica nada antes de las 18:00** (es el día de revisión del dueño): ese día solo la
  historia a las 18:00 y el post a las 20:30. De martes a domingo, los horarios normales.
- Horarios: usa los de `config/estrategia.md` §5 (jueves/viernes tarde a las 18:30) y conviértelos con
  `python scripts/when.py "AAAA-MM-DD HH:MM"` (zona horaria correcta). El mejor reel de la semana va jueves o viernes.
- Reparte los pilares de contenido de la persona. Cada publicación con un objetivo claro
  (alcance, guardados, comentarios o seguidores).

## 6. Escribir la cola (`queue/<id>.json`, un archivo por publicación)
Reglas de calidad:
- **Reels (15–35 s, 4–8 escenas):** la escena 1 es el gancho (texto en pantalla de máx. 7 palabras y
  narración que genere curiosidad en <2 s). Una idea por escena. Cierre con llamado a la acción
  (comentar, guardar o seguir). **Sin voz** (no escribas `narration`: al dueño no le gusta la voz artificial). Usa `music` si hay temas en `assets/music/`.
- **Carruseles (5–8 láminas):** lámina 1 = promesa clara; láminas de texto con `"source": "card"`
  (colores de marca consistentes en `bg`/`bg2`); última lámina = resumen o llamado a la acción.
- **Imágenes:** una idea fuerte, texto corto encima o ninguno.
- **Historias (1 diaria):** avisos del post del día, preguntas, detrás de escena. Imagen con texto corto.
- **Visuales:**
  - **Diseños con IA (`source: diseno`)**: úsalos en la portada/gancho de cada reel (y en todas sus escenas con foto
    si quieres el reel completo diseñado, siempre con el MISMO estilo), en las historias con foto y en la primera
    lámina de los carruseles. Elige el `estilo` SOLO entre los `aprobados` de `config/estilos.json`, alternándolos (ver `config/marca.md`).
    Pon los textos en `kicker`, `text`, `subtext` y `cta` (cortos). Al revisar las vistas previas, comprueba que la
    IA escribió bien los textos y que el diseño no es genérico; si falla, corrige con `"replace": true`.
  - **Prioridad:** 1) `material/listos/` (se publica tal cual) · 2) fotos y videos propios de `material/`
    (videos con `keep_audio: true` y sin `duration` si se usan completos) · 3) tarjetas `card` con la paleta
    de `config/marca.md` (`bg`: rojo/beige/arena, `logo: true`) · 4) IA solo si falta material de ambiente.
  - **Retoque de fotos propias:** todas llevan retoque local suave (automático). En la foto más importante de
    cada reel, carrusel e historia agrega `"ia_edit": "luz"` (la API mejora luz y color sin cambiar nada más).
    En comida, tragos y detalles de `servicios/` u `otros/` puedes usar `"ia_edit": "fondo"` o una instrucción
    libre en inglés. En `habitaciones/` y `espacios/` SOLO "luz". Al revisar las vistas previas compara con la
    original: si la IA cambió algo además de la luz (muebles, cuadros, tamaño), quita `ia_edit` con `"replace": true`.
  - Portadas: si hay una que calce en `material/portadas/`, úsala con `"cover"`. Si falta, anota en el resumen
    qué portadas conviene que el dueño haga (tema y texto sugerido).
  - Cierra cada reel con una tarjeta roja con el logo al centro (`"logo": true, "logo_position": "center"`, 2 s).
  - Textos sobre la imagen: título corto (máx. 7 palabras) en `text` y, si hace falta, detalle en `subtext`.
  - `ia` (imagen IA; usa OpenAI si está la clave, si no Pollinations): `prompt` en **inglés** escrito como
    foto de revista: sujeto concreto, materiales, luz (warm tungsten, candlelight, golden hour), lente
    (35mm, shallow depth of field), encuadre vertical, paleta (deep burgundy, warm gold, soft cream).
    Paleta de la marca (burgundy red, warm cream, beige, muted gold) para que el perfil se vea coherente. Solo ambientes y detalles genéricos
    (velas, copas, sábanas, vapor, ciudad de noche); **nunca** para representar el hotel o sus habitaciones.
    Nada de personas reales, logos, marcas, texto dentro de la imagen ni nada sugerente.
    `"quality": "high"` solo para la portada o el gancho del reel más importante de la semana.
  - `pixabay_video` / `pixabay_photo` (si existe la clave): `query` corto en inglés.
  - `card`: para frases y listas.
  - `file` con `"path": "material/..."`: fotos y videos reales del hotel (obligatorio para mostrar habitaciones).
- **Caption:** primera línea = gancho; 2–4 líneas de valor con palabras clave locales (ver estrategia §6);
  llamado a la acción; **3–5 hashtags** al final (Instagram no permite más de 5).
- **alt_text** en imágenes y carruseles: describe la foto con palabras clave (ej. "Habitación con jacuzzi privado en Providencia").
- Cada reel con una razón para **enviárselo a la pareja** y gancho en los primeros 2 segundos (estrategia §2–3).
- No inventes datos: si das cifras o consejos, que vengan de lo que investigaste en el paso 3.
- `id` = `AAAA-MM-DD-tipo-tema` (minúsculas y guiones). `status` = `"planned"`.

Luego ejecuta `python scripts/validate_queue.py` y corrige hasta que todo esté ✅.

## 7. Subir
```bash
git checkout -b claude/lote-<AAAA-MM-DD del lunes>
git add queue reviews config/promos.json && git commit -m "Lote semanal <fecha>" && git push -u origin HEAD
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

## 9. Issue de revisión
El Action de render crea solo el issue **"Revisión · semana del <lunes>"** con una casilla y la vista previa
de cada publicación. Para que el dueño vea tu resumen ahí, incluye en la rama del lote (paso 7) el archivo
`reviews/<AAAA-MM-DD del lunes>-resumen.md` con el resumen del paso 10: el Action lo publica como comentario.

## 10. Resumen final
Escribe un resumen breve: qué se programó (fecha, tipo, tema), qué aprendiste del informe y
cualquier cosa que el dueño de la cuenta deba revisar en la app (mensajes marcados para revisión),
qué material conviene subir, y **una acción de crecimiento** de la estrategia §7 para esa semana.
