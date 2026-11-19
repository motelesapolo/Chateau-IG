# Guía desde cero (≈ 60–90 minutos, una sola vez)

Al terminar tendrás una cuenta de Instagram que publica sola, responde comentarios y
mensajes, y que Claude alimenta cada semana. **Costo: $0** (solo necesitas el plan de Claude
que ya usas para Claude Code).

Vas a crear 5 cosas, en este orden:

| # | Qué | Para qué | Costo |
|---|---|---|---|
| 1 | Cuenta de Instagram profesional | La cuenta que se va a manejar | Gratis |
| 2 | App de Meta (developers.facebook.com) | Permiso oficial para publicar y responder | Gratis |
| 3 | Cuenta de GitHub + este repo | Donde viven el código, la cola y los robots | Gratis (repo público) |
| 4 | Claves gratis: Groq (+ Pixabay opcional) | IA que responde la bandeja / videos de stock | Gratis |
| 5 | Tarea programada semanal en Claude Code | Claude crea el contenido cada domingo | Incluido en tu plan |

> 🔒 **Nunca pegues tokens ni claves en el chat.** Siempre van en GitHub → Secrets (paso 6).

---

## Paso 1 · Crear la cuenta de Instagram (10 min)

1. En el celular, abre Instagram → **Crear cuenta nueva**. Usa un correo nuevo o uno que no tenga
   otra cuenta asociada. Elige el nombre de usuario de la cuenta.
2. Pon foto de perfil, nombre y biografía (Claude te puede proponer textos).
3. Hazla **pública**: Configuración → Privacidad de la cuenta → desactiva "Cuenta privada".
4. Pásala a **profesional, tipo Empresa (Business)**:
   Configuración → *Tipo de cuenta y herramientas* → **Cambiar a cuenta profesional** →
   elige una categoría → **Empresa**. (Empresa en vez de Creador porque las historias por API
   han estado limitadas a cuentas de empresa.) No hace falta conectar una página de Facebook.
5. Si la cuenta va a ser un **personaje inventado por IA**, activa la etiqueta de perfil
   generado por IA en la configuración del perfil. Sin ella Instagram le quita alcance.
6. Úsala un poco "como humano" los primeros días (sube 1–2 fotos a mano, completa el perfil).
   Las cuentas recién creadas que publican de inmediato por API se ven sospechosas.

## Paso 2 · Crear la app de Meta (20 min)

1. Entra a **developers.facebook.com** con una cuenta de **Facebook** (es obligatorio tener una;
   puede ser la tuya personal, no se publica nada en ella) → **Comenzar / Get Started** y completa
   el registro como desarrollador (verifica tu correo/teléfono).
2. **Crear app** (Create App):
   - Conectar un negocio: **"No quiero conectar un portafolio comercial por ahora"** → Siguiente.
   - Caso de uso: **Otro** (Other) → Siguiente.
   - Tipo de app: **Negocios** (Business) → Siguiente.
   - Nombre de la app (ej. "piloto-mi-cuenta") y tu correo → **Crear app**.
3. En el panel de la app, busca el producto **Instagram** → **Configurar** (Set up).
   Se agrega "API setup with Instagram login".
4. En **Instagram → API setup with Instagram login**, sección **"1. Generate access tokens"**:
   - **Add account** → inicia sesión con la cuenta de Instagram del paso 1 y acepta los permisos.
   - Si te lo pide, en la app de Instagram acepta la invitación de evaluador
     (Configuración → Apps y sitios web → Invitaciones de evaluador).
   - Junto a la cuenta, presiona **Generate token**, acepta, y **copia el token** (empieza con `IG...`).
     Guárdalo un momento en un lugar seguro (lo pegarás en el paso 6). Dura 60 días; el sistema
     lo renueva solo cada semana.
5. Revisa que en la lista de permisos estén: `instagram_business_basic`,
   `instagram_business_content_publish`, `instagram_business_manage_comments`,
   `instagram_business_manage_messages` (y `instagram_business_manage_insights`).

> No necesitas "App Review" ni verificación de negocio: la app solo maneja **tu** cuenta, y para eso
> basta el acceso estándar. Si más adelante los DMs no llegan desde usuarios comunes, mira
> "Problemas frecuentes" al final.

## Paso 3 · Crear la cuenta de GitHub y el repositorio (10 min)

1. Crea una cuenta en **github.com** (gratis).
2. Arriba a la derecha **+ → New repository**:
   - Nombre: por ejemplo `mi-instagram`.
   - Visibilidad: **Public** ← importante: así GitHub Actions es gratis e ilimitado y la CDN
     puede servir las imágenes a Instagram. (No se guarda nada privado: ni mensajes ni tokens.)
   - Deja todo lo demás vacío → **Create repository**.
3. Vuelve al chat con Claude y dile: *"Ya creé el repo `TU_USUARIO/mi-instagram`, súbelo"*.
   Claude conectará GitHub (te pedirá autorizar la app de Claude en GitHub) y subirá todos los archivos.

## Paso 4 · Claves gratis (10 min)

- **Groq (obligatoria, responde la bandeja):** entra a **console.groq.com** → crea cuenta (sin tarjeta)
  → **API Keys → Create API Key** → copia la clave (`gsk_...`).
- **Pixabay (opcional, fotos y videos de stock gratis):** crea cuenta en **pixabay.com** → abre
  **pixabay.com/api/docs/** con la sesión iniciada → tu clave aparece en la sección "Parameters" (`key`).
- **Pollinations (opcional, quita límites/marca de agua de las imágenes IA):** **auth.pollinations.ai**
  → inicia sesión con GitHub → copia tu token.

## Paso 5 · Token de GitHub para renovar el token de Instagram solo (5 min)

1. GitHub → tu foto → **Settings → Developer settings → Personal access tokens → Fine-grained tokens
   → Generate new token**.
2. Nombre: `renovar-token-ig`. Expiración: la máxima permitida (anota la fecha para renovarlo).
3. **Repository access → Only select repositories →** elige `mi-instagram`.
4. **Permissions → Repository permissions → Secrets: Read and write**.
5. **Generate token** → copia el token (`github_pat_...`).

## Paso 6 · Guardar los secretos en GitHub (5 min)

En tu repo: **Settings → Secrets and variables → Actions → New repository secret**, uno por uno:

| Nombre (exacto) | Valor |
|---|---|
| `IG_ACCESS_TOKEN` | Token de Instagram del paso 2 |
| `GROQ_API_KEY` | Clave de Groq |
| `GH_PAT` | Token de GitHub del paso 5 |
| `PIXABAY_KEY` | (opcional) clave de Pixabay |
| `POLLINATIONS_TOKEN` | (opcional) token de Pollinations |

Luego, en la pestaña **Variables** (al lado de Secrets) → **New repository variable**:
`DRY_RUN` = `1`. Esto deja todo en **modo simulación** la primera semana: el sistema decide qué
publicar y qué responder, pero no envía nada. Lo quitas en el paso 9.

## Paso 7 · Completar la personalidad de la cuenta (10 min, con Claude)

Edita `config/persona.md` (o pídele a Claude que lo complete contigo): nicho, público, tono,
pilares de contenido, preguntas frecuentes y el mensaje de crisis. Mientras quede algún
`[COMPLETAR]`, ni la bandeja ni el lote semanal se ejecutan.

## Paso 8 · Revisar que todo esté conectado (2 min)

Repo → pestaña **Actions** → **0 · Revisar configuración** → **Run workflow**.
Debe salir todo en ✅. Si algo sale en ❌, el mensaje dice qué falta.

## Paso 9 · Primer lote y encendido (15 min)

1. En **claude.ai/code** abre una sesión con tu repo y escribe: `/lote-semanal`.
   Claude investiga, planifica la semana, crea los guiones y los sube. GitHub genera las imágenes y
   videos (≈ 10–20 min). Revisa las vistas previas en `media/<id>/preview.jpg`.
2. En **Actions → 2 · Publicar a su hora → Run workflow**: en modo simulación verás en el resumen
   qué se publicaría.
3. Cuando estés conforme, **borra la variable `DRY_RUN`** (Settings → Secrets and variables →
   Variables). Desde ese momento publica y responde de verdad.

## Paso 10 · Dejar el lote semanal en automático (5 min)

En **claude.ai/code/routines** → **New routine** (o pídeselo a Claude en el chat):
- Repositorio: `mi-instagram`.
- Horario: **domingos ~20:40** (hora de Chile), después del informe semanal de las 18:00.
- Instrucción: `Sigue al pie de la letra .claude/commands/lote-semanal.md`.
- No hace falta activar "Allow unrestricted branch pushes": Claude sube a una rama `claude/...`
  y GitHub la incorpora sola.

¡Listo! Desde aquí:
- **Domingo 18:00** → informe con métricas (`reports/`).
- **Domingo ~20:40** → Claude crea la semana siguiente y revisa la calidad.
- **Cada 15 min** → se publica lo que toca.
- **Cada hora** → se responden comentarios y DMs.
- **Lunes** → se renueva el token.

Tu única tarea: mirar de vez en cuando la app de Instagram por si hay mensajes que el bot marcó
para revisión humana (propuestas comerciales, quejas serias, crisis). El informe semanal te dice cuántos hay.

---

## Problemas frecuentes

- **"Falta la variable IG_ACCESS_TOKEN"** → el secreto no está o tiene otro nombre (paso 6).
- **El token venció (error 190)** → genera uno nuevo como en el paso 2.4 y reemplaza el secreto.
  Si pasa seguido, revisa que exista `GH_PAT` y que **5 · Renovar token** termine en verde.
- **Los DMs de usuarios comunes no aparecen o no se pueden responder** → la app sigue en modo
  desarrollo. Pasa la app a **Live** (Publicar) en el panel de Meta: te pedirá una URL de política de
  privacidad (usa la de `PRIVACY.md` de tu repo: `https://github.com/TU_USUARIO/mi-instagram/blob/main/PRIVACY.md`)
  y, si Meta lo exige, solicita acceso avanzado a `instagram_business_manage_messages` en App Review.
- **Un video quedó en `render_failed` o `publish_failed`** → el campo `error` del JSON en `queue/`
  explica la causa; el lote del domingo lo revisa y corrige.
- **GitHub dejó de ejecutar los horarios** → GitHub pausa los horarios de repos sin actividad por
  60 días; el lote semanal hace commits, así que no debería pasar. Si pasa: Actions → reactivar.
- **Quiero pausar todo** → Actions → elige el workflow → "…" → **Disable workflow**.
