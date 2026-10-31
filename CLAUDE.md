# AOVE al Día

Web estática de precios y noticias del aceite de oliva. Python 3.12 + Jinja2 → `docs/` (GitHub Pages). Todo en español: código, comentarios, textos y mensajes.

## Mapa
- `diario.py`: punto de entrada (precios → noticias → artículos → web). `--solo-web` solo regenera `docs/`.
- `config.py`: nombre, modelos de Gemini, límites, opción `PUBLICAR_PRECIOS_INFAOLIVA`.
- `aove/fuentes/{oleista,infaoliva}.py`: scrapers. `aove/red.py`: descargas (robots.txt, pausa de 2 s).
- `aove/redactor.py`: selección y redacción con Gemini (usa `services/agent_aove/gemini.py`; salida estructurada, y una cifra o fecha que no esté en la fuente impide publicar).
- `aove/almacen.py`: lectura y escritura de `datos/`. `aove/web.py`: datos → plantillas.
- `plantillas/`: Jinja2 (`_grafica`, `_precios` y `_tarjeta` son parciales). `estaticos/`: `estilo.css`, `precios.js` (Chart.js), logos, iconos y `manifest.webmanifest`.
- `logo/`: PNG original del logo. `marca/generar_logo.py` crea a partir de él los logos e iconos de `estaticos/`. `marca/index.html`: hoja de marca (servidor `marca` de `.claude/launch.json`, en `/marca/`). `pc/actualizar.py`: tarea real, en el PC (Oleista da 403 desde GitHub): sincroniza, ejecuta y sube a GitHub; registro en `pc/registro.log`. `pc/programar_tareas.ps1` crea las tareas de Windows: cada 30 min de 07:00 a 22:00, y ejecución completa al iniciar sesión y a las 22:30. `.github/workflows/diario.yml`: solo manual. Los artículos se publican una sola vez al día. Web: https://manurml.github.io/web_oliva/

- `services/agent_aove/`: análisis diario con Gemini (`.github/workflows/daily_aove.yml`, 07:00 UTC). Lee precios y noticias guardados, sin descargar de las fuentes. Una cifra o fecha sin respaldo en los datos deja el artículo en `draft`.

- `services/agent_instagram/`: tras cada ejecución de `pc/actualizar.py`, si hay precios o artículos nuevos, prepara en `instagram/AAAA-MM-DD/` (local, no se sube) carrusel, historias y textos para subirlos a mano. No publica nada. Cifras de las imágenes: de los datos. Textos: Gemini, con revisión de cifras y longitudes. Solo usa artículos redactados, nunca fichas breves. Plantilla: `plantillas/instagram.html`.

## Comandos
- Contenido de Instagram: `python -m services.agent_instagram` (`--forzar` genera aunque no haya novedades, `--solo-imagenes` repite las imágenes con los textos guardados, `--seco` muestra el contexto)
- Artículo de análisis: `python -m services.agent_aove` (`--seco` muestra el contexto, `--borrador` no lo publica)
- Regenerar la web: `python diario.py --solo-web`
- Ejecución completa (red; redacta con Gemini si hay `GEMINI_API_KEY`): `python diario.py`
- Comprobar: `python -m pyflakes aove services diario.py config.py` y `node --check estaticos/precios.js`
- Ver la web: servidor `web` de `.claude/launch.json` (puerto 8765, sirve `docs/`)

## Reglas
- No leas ni edites `docs/`: se genera. Cambia `plantillas/` o `estaticos/` y regenera.
- No leas enteros `datos/*.json` (bloqueado en `.claude/settings.json`). Consúltalos con `python -c` o con `aove.almacen`.
- No ejecutes `python diario.py` completo sin clave de API para hacer pruebas: publicaría fichas breves y gastaría las noticias candidatas. Prueba en una copia o con `--solo-web`.
- Precios de InfaOliva: no se publican sin su autorización (su web lo prohíbe). No uses su `/funciones/ajax.php` (bloqueado por su robots.txt).
- Diseño: basado en la maqueta `minimalismo_bot_nico_aove.html` (local, no se publica): fondo verde pálido, tarjetas blancas de 24 px, Bodoni Moda + Outfit, acento dorado, cabecera flotante. Orden de la portada: tarjeta de precio con gráfica pequeña y presentación, gráfica comparativa, noticias. Los colores de las series están validados para daltonismo; no los cambies sin volver a validarlos. Modo oscuro con tokens en `:root`. `tabular-nums` solo en `.tabla`. Sin datos ni funciones de ejemplo de la maqueta.
- Accesibilidad (Web Interface Guidelines): botones con `aria-pressed`, `&nbsp;` antes de `€/kg` y `%`, número y fecha con `Intl`, región y periodo en la URL.
- Commits solo si se piden.
