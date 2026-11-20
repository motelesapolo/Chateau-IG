# Pruebas de la API de ChatGPT

Para probar el retoque con fotos reales, Claude (o tú) edita `pedido.json` y lo sube a `main`:

```json
{"fotos": [{"path": "material/habitaciones/vip/foto.jpg", "modo": "luz"}],
 "generar": ["Candlelit bathtub detail, rose petals, warm steam"]}
```

El Action **7 · Probar API de ChatGPT** deja en `resultados/` una comparación por foto
(original · retoque gratis · ChatGPT) y `resumen.md` con qué motor se usó. No publica nada en Instagram.
