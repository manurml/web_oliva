# AOVE al Día

Web estática de precios y noticias del aceite de oliva. Python 3.12 + Jinja2 → `docs/` (GitHub Pages). Todo en español: código, comentarios, textos y mensajes.

## Mapa
- `diario.py`: punto de entrada (precios → noticias → artículos → web). `--solo-web` solo regenera `docs/`.
- `config.py`: nombre, modelo de Claude, límites, opción `PUBLICAR_PRECIOS_INFAOLIVA`.
- `aove/fuentes/{oleista,infaoliva}.py`: scrapers. `aove/red.py`: descargas (robots.txt, pausa de 2 s).
- `aove/redactor.py`: selección y redacción con Claude (salida estructurada, `fallbacks="default"`).
- `aove/almacen.py`: lectura y escritura de `datos/`. `aove/web.py`: datos → plantillas.
- `plantillas/`: Jinja2 (`_grafica`, `_precios` y `_tarjeta` son parciales). `estaticos/`: `estilo.css`, `precios.js` (Chart.js), `favicon.svg`.
- `marca/`: logo (SVG) y hoja de marca. `.github/workflows/diario.yml`: cada 30 min (05-20 UTC) con `--si-hay-cambios`, y ejecución completa a las 21:00 UTC. Los artículos se publican una sola vez al día.

## Comandos
- Regenerar la web: `python diario.py --solo-web`
- Ejecución completa (red; redacta con Claude si hay `ANTHROPIC_API_KEY`): `python diario.py`
- Comprobar: `python -m pyflakes aove diario.py config.py` y `node --check estaticos/precios.js`
- Ver la web: servidor `web` de `.claude/launch.json` (puerto 8765, sirve `docs/`)

## Reglas
- No leas ni edites `docs/`: se genera. Cambia `plantillas/` o `estaticos/` y regenera.
- No leas enteros `datos/*.json` (bloqueado en `.claude/settings.json`). Consúltalos con `python -c` o con `aove.almacen`.
- No ejecutes `python diario.py` completo sin clave de API para hacer pruebas: publicaría fichas breves y gastaría las noticias candidatas. Prueba en una copia o con `--solo-web`.
- Precios de InfaOliva: no se publican sin su autorización (su web lo prohíbe). No uses su `/funciones/ajax.php` (bloqueado por su robots.txt).
- Diseño: minimalista. Orden de la portada: gráfica, precios, noticias. Tipografía Schibsted Grotesk. Los colores de las series están validados para daltonismo; no los cambies sin volver a validarlos. Modo oscuro con tokens en `:root`. Patrones (ideas de Subframe): título de sección con subtítulo gris, etiqueta `.estado` con punto verde, baldosas grises para los precios, fuente y fecha encima del titular. `tabular-nums` solo en `.tabla`: en esta fuente ensancha comas y dos puntos.
- Accesibilidad (Web Interface Guidelines): botones con `aria-pressed`, `&nbsp;` antes de `€/kg` y `%`, número y fecha con `Intl`, región y periodo en la URL.
- Commits solo si se piden.
