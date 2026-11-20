# Marca de Hotel Le Chateau

> Identidad fija: no se cambia de una semana a otra. Lo que varía son las ideas, los formatos y los ganchos.
> Los valores que usa el sistema están en `config/settings.json` → `brand`.

## Logo
- `assets/brand/logo.png` (original, fondo rojo) y `assets/brand/logo_crema.png` (letras crema, fondo transparente).
- En tarjetas: `"logo": true`. No deformar, no cambiar colores salvo crema sobre rojo o rojo sobre fondo claro.

## Paleta
| Nombre | Hex | Uso |
|---|---|---|
| rojo | `#811721` | Color principal: fondos de tarjetas, recuadros de texto, logo sobre claro |
| crema | `#FCF1E1` | Texto sobre rojo o sobre fotos, logo |
| beige | `#F3D8B9` | Fondos claros (promos, precios, carruseles informativos) |
| arena | `#F5DFC5` | Fondo claro alternativo / degradados con beige |
| dorado | `#9C6A2B` | Detalles: líneas, íconos, precios. Nunca como fondo grande |
| cafe | `#2A1C14` | Texto secundario sobre fondos claros |

Combinaciones: **crema sobre rojo** (la principal) · **rojo + café sobre beige/arena** con detalles dorados.
Nada de negro puro, blancos fríos, azules ni colores neón.

## Tipografías
- **Títulos: Playfair Display** (`assets/fonts/PlayfairDisplay[wght].ttf`, peso Medium), en minúsculas normales
  (no todo en mayúsculas). La palabra destacada va en **Playfair Display Italic** (`PlayfairDisplay-Italic[wght].ttf`),
  en dorado o crema. Elegida por el dueño el 20-11-2026: se usa hasta nuevo aviso.
- **Textos: Manrope** SemiBold (`assets/fonts/Manrope[wght].ttf`).
- **Tulpen One / letra del logo: SOLO en el logo.** Nunca en títulos ni textos.
- Máximo estas dos (más el logo). Licencia SIL Open Font License (archivos OFL en `assets/fonts/`).

## Fotos y videos
- Los hace el dueño (y los edita con ChatGPT): luz cálida, tonos crema/dorado, ambiente ordenado.
- Retoque permitido: luz, color, nitidez. Prohibido agregar o quitar elementos de las habitaciones.
- Portadas de reels: hechas por el dueño con ChatGPT en `material/portadas/`, con esta paleta y tipografías,
  lo importante en el centro (el perfil las recorta a 3:4).

## Plantillas que arma el sistema
Las de `config/linea-editorial.md` (foto + frase, serie, gráfica de marca, detalle). Toda la tipografía la pone el
sistema (Playfair Display + Manrope); la IA nunca escribe texto en las imágenes.

## Uso de la API de ChatGPT
- **Fotos:** retoque de luz y color. Se copia solo su corrección de color sobre la foto original (la habitación no
  cambia en nada: ni encuadre, ni letreros, ni muebles).
- **Fondos de las gráficas de marca:** terciopelo, satén, dorado líquido, formas 3D y líneas art déco en la paleta,
  **sin texto**. Reglas en `config/estilos.json`.
- Los diseños completos hechos por la IA (`source: diseno`) quedaron descartados por la línea editorial.
