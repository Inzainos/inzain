# InZain — Fractal Core (v11)

Navegador de escritorio "soberano" construido sobre **PyQt6 + QtWebEngine**
(motor Chromium embebido). Autor: Elán Zainos Corona (Fractal Core Research).

Características distintivas:

- **Árbol fractal de pestañas** — las pestañas se organizan como nodos padre/hijo
  en un panel lateral, no como una tira horizontal.
- **HUD de telemetría** — CPU / RAM / RED en vivo (vía `psutil`), con modo normal
  y modo mini colapsado.
- **Escudo de red** — interceptor que bloquea dominios de tracking/ads a nivel de
  request (configurable).
- **Purga visual** — botón que elimina banners, pop-ups y ruido del DOM de la
  página actual.
- **Lectura por voz (TTS)** — lee el contenido de la página en voz alta.
- **Sesión persistente cifrada** — el árbol de pestañas se guarda entre arranques
  (cifrado con Fernet si `cryptography` está disponible; JSON plano si no).
- **Tema cyberpunk** — verde/negro monoespaciado.

## Estructura

```
inzain/
├── main.py            Punto de entrada + AppController (cableado y navegación)
├── inzain_core.py     Motor web, escudo, TTS, sonido, gestor de sesión
├── inzain_ui.py       Ventana, HUD, barra de herramientas, árbol fractal
├── urls.py            Resolución de URL (sin Qt → testeable)
├── config.py          Configuración central + flags de seguridad
├── logging_setup.py   Logging rotativo a archivo + consola (siempre activo)
├── requirements.txt
├── conftest.py
├── assets/            splash_fractal_core.png, fractal.ico (colócalos aquí)
├── tests/
│   └── test_smoke.py  Tests headless (no requieren GUI)
├── AGENTS.md
└── .gitignore
```

## Instalación

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> El `python` del sistema no tiene `PyQt6-WebEngine`: ejecutar siempre con
> `.venv/bin/python` o con `./run.sh` (que lo exige).

Coloca `splash_fractal_core.png` y `fractal.ico` dentro de `assets/`
(el arranque funciona igual si faltan: se omiten con un aviso en el log).

## Ejecución

```bash
./run.sh          # o: .venv/bin/python main.py
```

Atajos: `Ctrl+T` nueva pestaña raíz · `Ctrl+Shift+T` nueva pestaña hija de la
activa (árbol fractal) · `Ctrl+W` cerrar · `Ctrl+B` colapsar panel ·
`F5` recargar · `Ctrl++` / `Ctrl+-` zoom.

## Configuración y seguridad

Todo el comportamiento sensible vive en `config.py` y puede sobreescribirse por
variable de entorno. **Lo que puede exponerte viene APAGADO por defecto.**

| Flag (env)                       | Default | Qué hace |
|----------------------------------|---------|----------|
| `INZAIN_ACCEPT_INVALID_CERTS`    | `False` | Aceptar certificados TLS inválidos. Actívalo SOLO para redes locales/dev — de lo contrario expone a MITM. |
| `INZAIN_ENABLE_SHIELD`           | `True`  | Bloqueo de trackers/ads a nivel de request. |
| `INZAIN_AUTO_GRANT_MEDIA`        | `False` | Conceder mic/cámara/captura sin preguntar. |
| `INZAIN_USE_FAKE_UA`             | `False` | User-Agent anti-detección (imita Chrome). |
| `INZAIN_ALLOW_INSECURE_CONTENT`  | `False` | Permitir contenido http dentro de https. |
| `INZAIN_HOME_URL`                | DuckDuckGo | Página de inicio. |
| `INZAIN_LOG_LEVEL`               | `INFO`  | Nivel de log (`DEBUG`/`INFO`/`WARNING`/…). |

Ejemplo (activar bypass TLS solo para una sesión de laboratorio local):

```bash
INZAIN_ACCEPT_INVALID_CERTS=1 python main.py
```

## Logs

El logging está **siempre activo**: escribe a `logs/inzain.log` (rotativo, 2 MB ×
5 archivos) y a la consola. Nivel configurable por `INZAIN_LOG_LEVEL`.

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```

Los tests de `urls.py` y `config.py` corren sin PyQt6 instalado; el test del
motor se salta automáticamente si Qt no está presente.

---

## Cambios en v11.1 (endurecimiento tras instalación y prueba real)

Verificado instalando el paquete desde cero en Linux/WSL2 y ejecutándolo.

**Seguridad**
- `inzain.key` se escribía con el umask del proceso (**0o644**): la clave Fernet
  que protege toda la sesión quedaba legible por cualquier usuario del sistema.
  Ahora los secretos nacen en **0o600** vía `os.open()` con el modo desde el
  primer byte — no `open()` + `chmod`, que deja una ventana en la que el archivo
  es legible por todos. Las claves creadas por versiones anteriores se corrigen
  al abrirlas, con aviso en el log.
- Mismo trato para `session_inzain.enc` y para `session_inzain.json` (que sin
  `cryptography` guarda la sesión **en claro**).

**Corrección de bugs**
- `_on_quit` cuelga de `aboutToQuit`, que Qt **no** emite cuando el proceso
  recibe una señal: un `kill`, un cierre de sesión del SO o un apagado perdían
  el árbol de pestañas sin dejar rastro. Ahora `SIGTERM`/`SIGINT` se traducen a
  `app.quit()`, que sí dispara el guardado. Hace falta además un `QTimer` que
  devuelva el control al intérprete cada 200 ms: sin él Qt bloquea dentro de
  C++ y el manejador de Python no llega a ejecutarse.

**Tests**
- 4 nuevos (14 en total). Validados por mutación: revertir el código al
  comportamiento anterior hace fallar los tres de permisos.

---

## Cambios en v11 (auditoría y mejora)

Partiendo del trío canónico `main.py + inzain_core.py + inzain_ui.py` (v10):

**Seguridad**
- El **bypass total de TLS** (`certificateError → acceptCertificate()` incondicional)
  pasó a ser un flag (`ACCEPT_INVALID_CERTS`, **por defecto rechaza** certificados
  inválidos y lo registra). Era un anti-patrón MITM shippeado por defecto.
- `AllowRunningInsecureContent` pasó de fijo `True` a flag (`False` por defecto).
- Los **permisos de mic/cámara/captura** ya no se conceden en automático: dependen
  de `AUTO_GRANT_MEDIA` (`False` por defecto).
- El **escudo de red**, que estaba **comentado** en v10, ahora se conecta de verdad
  vía `ENABLE_SHIELD` y con blacklist ampliada.

**Corrección de bugs**
- `restore_session` en v10 solo restauraba los hijos del **último** nodo (error de
  indentación). Corregido: ahora recursa por cada nodo con su padre correcto.
- `remove_node` (que venía truncado) quedó completo y saca el nodo raíz por índice.

**Ingeniería**
- Configuración centralizada en `config.py` (antes: valores dispersos y hardcodeados).
- **Logging rotativo a archivo** en `logging_setup.py` (v10 solo tenía consola a
  nivel WARNING; ahora INFO a archivo + consola, cumpliendo "siempre generar logs").
- `resolve_url` extraído a `urls.py` sin dependencias de Qt → **testeable headless**;
  además ahora URL-encodea la búsqueda y cubre IPs `192.168.*`.
- Suite de tests headless (`tests/test_smoke.py`).
- `except:` desnudos reemplazados por `except Exception` con log.
- Rutas de assets movidas a `assets/` y guardadas ante ausencia.
