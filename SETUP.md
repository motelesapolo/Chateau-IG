# Guía desde cero (≈ 60–90 minutos, una sola vez)

Al terminar tendrás una cuenta de Instagram que publica sola, responde comentarios y mensajes,
y que Claude alimenta cada semana. **Costo: $0** (solo el plan de Claude que ya usas).

| # | Qué | Para qué | Costo |
|---|---|---|---|
| 1 | Cuenta de Instagram profesional (Empresa) | La cuenta que se va a manejar | Gratis |
| 2 | App de Meta con "Unified login" | Permiso oficial para publicar y responder | Gratis |
| 3 | Cuenta de GitHub + este repo (público) | Donde viven el código, la cola y los robots | Gratis |
| 4 | Clave de Groq (+ Pixabay opcional) | IA que responde la bandeja / stock | Gratis |
| 5 | Tarea semanal en Claude Code | Claude crea el contenido cada domingo | Incluido |

> 🔒 **Nunca pegues tokens ni claves en un chat.** Siempre van en GitHub → Secrets (paso 6).

---

## Paso 1 · Cuenta de Instagram (10 min)
1. Crea la cuenta desde la app (correo sin otra cuenta asociada).
2. Hazla **pública** (Configuración → Privacidad de la cuenta).
3. Pásala a **profesional → Empresa** (Configuración → Tipo de cuenta y herramientas). No hace falta página de Facebook.
4. Si la cuenta fuera un personaje inventado por IA, activa la etiqueta de perfil generado por IA.

## Paso 2 · App de Meta (20 min)
Las apps nuevas de Meta solo ofrecen **"API setup with Unified login"** (Facebook Login for Business).
No necesita página de Facebook, pero sí un **portfolio comercial** (gratis).

1. **developers.facebook.com** → inicia sesión con Facebook → regístrate como desarrollador.
2. **Crear app** → caso de uso **Otro** → tipo **Negocios** → nombre sin la palabra "Instagram" (ej. `lechateau-piloto`).
3. Agrega el producto **Instagram → Configurar**.
4. Menú izquierdo **Instagram → API setup with Unified login**:
   - Si pide **portfolio comercial**: "+ Portfolio comercial" → crea uno (nombre del negocio, tu nombre, correo) y confírmalo por correo.
   - **1. Configurar tu app** → **Crear nueva configuración** con: variación *General*, token *de usuario del sistema (SUAT)*,
     caducidad *Nunca*, activo *tu cuenta de Instagram*, permisos `instagram_basic`, `instagram_content_publish`,
     `instagram_manage_comments`, `instagram_manage_messages` (los `ads_*` que vienen por defecto no molestan).
   - **URL de redireccionamiento:** `https://localhost/` → guardar.
5. **Roles de la app → Roles** → agrega la cuenta de Instagram como **Evaluador de Instagram** y acepta la invitación
   (instagram.com → Configuración → Apps y sitios web → Invitaciones de evaluador).
6. Vuelve a **API setup with Unified login → 2. Generar tokens de acceso** → agrega la cuenta.
   **El token se genera recién en el paso 6**, para pegarlo directo en GitHub.
7. Salta "3. Webhooks" y "4. Revisión de la app". Deja la app en modo **Development**.

## Paso 3 · GitHub (10 min)
1. Crea una cuenta en **github.com**.
2. **+ → New repository** → nombre (ej. `lechateau-ig`) → **Public** → sin README → **Create repository**.
   (Público = Actions gratis e ilimitado y las imágenes se pueden servir a Instagram. Nunca se guardan mensajes ni tokens.)
3. Dile a Claude el nombre del repo: él lo conecta y sube todos los archivos.

## Paso 4 · Claves gratis (10 min)
- **Groq (obligatoria):** console.groq.com → API Keys → Create API Key.
- **Pixabay (opcional, stock):** pixabay.com/api/docs con la sesión iniciada → tu `key`.
- **Pollinations (opcional, más imágenes IA sin límites):** auth.pollinations.ai → token.

## Paso 5 · Completar la personalidad (10 min, con Claude)
`config/persona.md`: negocio, servicios, precios, cómo reservar, tono, preguntas frecuentes.
Mientras quede algún `[COMPLETAR]`, la bandeja y el lote semanal no se ejecutan.

## Paso 6 · Generar el token y guardar los secretos (10 min)
1. Abre en otra pestaña tu repo → **Settings → Secrets and variables → Actions → New repository secret**.
2. En Meta → **API setup with Unified login → 2. Generar tokens de acceso** → **Generar token** junto a la cuenta → cópialo.
3. Pégalo en GitHub como secreto **`IG_ACCESS_TOKEN`** → *Add secret*. Cierra la ventana del token.
4. Agrega también:

| Secreto | Valor |
|---|---|
| `GROQ_API_KEY` | clave de Groq |
| `PIXABAY_KEY` | (opcional) |
| `POLLINATIONS_TOKEN` | (opcional) |

5. Pestaña **Variables → New repository variable**: `DRY_RUN` = `1` (modo simulación: decide pero no publica ni responde).

## Paso 7 · Revisar la conexión (2 min)
Repo → **Actions → 0 · Revisar configuración → Run workflow**. Todo debe salir ✅
(el resumen muestra el @ y el ID de la cuenta encontrada). Si falla con "No se encontró la cuenta",
crea la variable `IG_USER_ID` con el ID de la cuenta de Instagram (Claude te ayuda a obtenerlo).

## Paso 8 · Primer lote y encendido
1. En **claude.ai/code**, abre una sesión con el repo y escribe `/lote-semanal`. Revisa las vistas previas en `media/<id>/preview.jpg`.
2. **Actions → 2 · Publicar a su hora → Run workflow**: en simulación verás qué se publicaría.
3. Conforme → **borra la variable `DRY_RUN`**. Desde ahí publica y responde de verdad.

## Paso 9 · Lote semanal automático
**claude.ai/code/routines → New routine** (o pídeselo a Claude): repo `lechateau-ig`, domingos ~20:40,
instrucción `Sigue al pie de la letra .claude/commands/lote-semanal.md`.

Rutina resultante: domingo 18:00 informe → domingo ~20:40 Claude crea la semana → cada 15 min se publica →
cada hora se responde la bandeja → lunes se revisa que todo siga conectado (GitHub te avisa por correo si falla).

---

## Problemas frecuentes
- **"Falta la variable IG_ACCESS_TOKEN"** → el secreto no está o tiene otro nombre.
- **Error 190 (token inválido)** → genera uno nuevo (paso 6.2) y reemplaza el secreto.
- **No llegan DMs de usuarios comunes** → la app está en *Development*. Hay que completar "4. Revisión de la app"
  para acceso avanzado a `instagram_manage_messages` y pasarla a *Activo*; pide una política de privacidad: usa
  `https://github.com/TU_USUARIO/lechateau-ig/blob/main/PRIVACY.md`.
- **Un contenido quedó en `render_failed` o `publish_failed`** → el campo `error` del JSON en `queue/` explica la causa.
- **Pausar todo** → Actions → elige el workflow → "…" → **Disable workflow**.
