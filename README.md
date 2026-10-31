# AOVE al Día

Web estática de noticias y precios del aceite de oliva virgen extra que se actualiza sola cada mañana:

1. **Precios**: lee las cotizaciones diarias en origen de Oleista (AOVE, virgen y lampante en España, Andalucía, Italia y Grecia), las guarda en `datos/precios.json` (el histórico crece cada día) y dibuja la gráfica de evolución.
2. **Noticias**: revisa las publicaciones nuevas de InfaOliva y Oleista, pide a Gemini que elija las 2 más relevantes y que redacte con ellas artículos propios que citan y enlazan la fuente original.
3. **Web**: genera las páginas en `docs/`, listas para publicar con GitHub Pages.

## Estructura

```
diario.py              Tarea diaria (punto de entrada)
config.py              Nombre de la web, modelo, límites y opciones
aove/fuentes/          Lectura de Oleista e InfaOliva
aove/redactor.py       Selección y redacción con Gemini
aove/web.py            Generación de la web
plantillas/            HTML (Jinja2)
estaticos/             CSS, gráfica (Chart.js) e icono
datos/                 Histórico de precios, noticias vistas y artículos publicados
docs/                  Web generada (lo que se publica)
```

## Probar en tu equipo

```bash
pip install -r requirements.txt
```

```bash
python diario.py
```

Sin `GEMINI_API_KEY` la web se genera igualmente, pero las noticias salen como fichas breves con enlace en lugar de artículos redactados. Para ver la web: abre `docs/index.html` o lanza `python -m http.server 8765 --directory docs`.

## Publicación y actualización automática

La web está en https://manurml.github.io/web_oliva/ (GitHub Pages, carpeta `docs/`). Oleista rechaza las peticiones desde los servidores de GitHub (error 403), así que la actualización corre en el PC:

- `pc/actualizar.py` trae los últimos cambios, ejecuta `diario.py` y sube `datos/` y `docs/` si algo ha cambiado. Lo que hace queda en `pc/registro.log`.
- `pc/programar_tareas.ps1` crea una tarea de Windows que hace una ejecución completa al día: a las 09:00 o al iniciar sesión, lo que ocurra antes.

El PC debe estar encendido y con la sesión iniciada. Si estaba apagado, la tarea se ejecuta al volver a encenderlo e iniciar sesión. Sin `GEMINI_API_KEY` en las variables de entorno, las noticias se publican como fichas breves.

## Ajustes útiles (`config.py`)

| Opción | Para qué |
|---|---|
| `SITIO_NOMBRE`, `SITIO_LEMA` | Nombre y lema de la web |
| `NOTICIAS_POR_DIA` | Artículos nuevos por mañana (2) |
| `DIAS_MAX_ANTIGUEDAD` | Antigüedad máxima de una noticia para reescribirla (30 días) |
| `MODELO_CLAUDE` | Modelo usado para redactar |
| `PUBLICAR_PRECIOS_INFAOLIVA` | Muestra también la tabla diaria de InfaOliva (ver aviso) |

## Avisos importantes

- **Precios de InfaOliva**: su web indica que queda prohibida la publicación de su información usando su nombre sin autorización previa. Por eso se guardan pero **no se publican** salvo que actives `PUBLICAR_PRECIOS_INFAOLIVA=1`, cosa que solo deberías hacer con su permiso.
- **Contenido de las fuentes**: los artículos se redactan con palabras propias, citan y enlazan la fuente y no copian su texto ni sus imágenes. Aun así, el `robots.txt` de Oleista excluye a los rastreadores de IA y conviene que hables con ambas fuentes si la web va a tener uso comercial.
- **Ritmo de publicación**: Oleista e InfaOliva publican pocas noticias al mes, así que habrá días sin artículos nuevos. Para garantizar contenido diario se pueden añadir más fuentes en `aove/fuentes/`.
- El scraper respeta `robots.txt`, se identifica y espera 2 segundos entre peticiones. Si las webs cambian su diseño habrá que ajustar los selectores de `aove/fuentes/`.
