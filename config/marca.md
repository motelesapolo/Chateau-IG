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
- **Títulos:** Tulpen One (`assets/fonts/TulpenOne-Regular.ttf`), en MAYÚSCULAS y espaciada. Es la más
  parecida al logo (alta, angosta, A con arco, estilo art déco). El logo es un dibujo propio: no se escribe con la fuente.
- **Textos:** Manrope SemiBold (`assets/fonts/Manrope[wght].ttf`), limpia y moderna.
- Máximo estas dos. Títulos de hasta ~7 palabras; el resto con Manrope.
- Licencia de ambas: SIL Open Font License (archivos OFL en `assets/fonts/`).

## Fotos y videos
- Los hace el dueño (y los edita con ChatGPT): luz cálida, tonos crema/dorado, ambiente ordenado.
- Retoque permitido: luz, color, nitidez. Prohibido agregar o quitar elementos de las habitaciones.
- Portadas de reels: hechas por el dueño con ChatGPT en `material/portadas/`, con esta paleta y tipografías,
  lo importante en el centro (el perfil las recorta a 3:4).

## Plantillas que arma el sistema
- **Reel/historia sobre foto o video:** título en Tulpen crema dentro de un recuadro rojo semitransparente,
  `subtext` opcional en Manrope.
- **Tarjeta roja:** fondo rojo, logo arriba, título crema, línea dorada con rombo, subtítulo.
- **Tarjeta clara:** fondo arena→beige, título rojo, línea dorada, texto café, logo rojo abajo.
- **Cierre de reel:** tarjeta roja con el logo al centro (1,5–2 s).

## Dirección de arte (diseños con la API de ChatGPT)
- Las piezas principales (portada/gancho de reels, historias, primera lámina de carruseles) se hacen con
  `"source": "diseno"`: la IA diseña la pieza completa y deja un hueco; ahí va **la foto real sin modificar**.
- **Nada genérico:** prohibido el "flyer de plantilla" (hojitas, fila de íconos en círculos, botón píldora, todo
  centrado y simétrico, cintas, letras manuscritas). Las reglas exactas están en `config/estilos.json`.
- **Estilos aprobados por el dueño** (`aprobados` en `config/estilos.json`): `poster-deco` (póster art déco años 20)
  y `noche-burdeos` (foto grande arriba que se funde en burdeos, esquinas doradas art déco). Solo se usan esos.
  `cine`, `suizo` y `collage` quedan para probar (con `"prueba": true`); `revista` NO le gustó.
  Un estilo por reel (todas sus escenas iguales); alternar los aprobados en el perfil.
- **Audio:** sin voz artificial (al dueño no le gustó). Reels con música de `assets/music/` cuando exista.
- Textos cortos y exactos: `kicker`, `text` (título), `subtext`, `cta`. Sin precios salvo promo vigente.
