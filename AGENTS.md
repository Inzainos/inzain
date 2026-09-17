# AGENTS.md — InZain / Fractal Core

Guía operativa para agentes de IA (Claude Code, Cursor, Copilot, Codex, etc.)
que trabajen en el navegador **InZain**. Archivo neutral que leen todas las
herramientas; el detalle completo está en `README.md`.

## Qué es

**InZain / Fractal Core** — navegador de escritorio en PyQt6 + QtWebEngine con
árbol fractal de pestañas, HUD de telemetría, escudo anti-tracking, purga visual,
TTS y sesión cifrada. Es un proyecto **independiente**: no forma parte de
Sentinel Omega ni comparte su pipeline de datos.

## Estructura

```
main.py            Entrada + AppController (cableado UI↔núcleo, navegación)
inzain_core.py     Motor web, escudo de red, TTS, sonido, SessionManager
inzain_ui.py       Ventana, HUD, toolbar, árbol fractal (solo widgets)
urls.py            resolve_url() — sin Qt, testeable
config.py          Configuración + flags de seguridad (env-overridable)
logging_setup.py   Logging rotativo (archivo + consola)
tests/             Tests headless (pytest)
assets/            splash + icono
```

## Comandos

```bash
# Instalar dependencias
python -m pip install -r requirements.txt

# Ejecutar (desde la raíz del proyecto)
python main.py

# Tests (headless; no requieren GUI)
python -m pytest tests/ -q

# Ejecutar activando un flag de seguridad para dev local
INZAIN_ACCEPT_INVALID_CERTS=1 python main.py
```

## Reglas duras (no romper)

1. **Comportamiento sensible solo por config/entorno.** TLS inválido, permisos de
   medios, UA falso y contenido inseguro se controlan con flags en `config.py`
   (prefijo `INZAIN_`) y vienen **apagados por defecto**. No los pongas fijos en
   `True` en el código.
2. **Siempre generar logs.** Todo camino relevante (arranque, nueva pestaña,
   navegación, permisos, TLS, guardado de sesión) debe registrar en el logger
   `InZain`. No usar `print`. No usar `except:` desnudo → `except Exception` + log.
3. **Nunca versionar secretos ni estado.** `inzain.key`, `session_inzain.*`,
   `inzain_data/` y `logs/` están en `.gitignore`. La clave de sesión jamás se sube.
4. **Lógica pura fuera de Qt.** Lo testeable (p. ej. resolución de URL) va en
   módulos sin dependencias de Qt (`urls.py`) para poder correr headless.
5. **La UI no navega.** `inzain_ui.py` solo construye widgets y expone
   `add_node`/`remove_node`; toda la lógica vive en `AppController` (`main.py`).
6. **Los tests deben pasar** antes de commitear cambios de código.

## Git y PRs

- Este proyecto es independiente de `sentinel_omega/`. Si se aloja en el monorepo
  `workspaces`, va en su propia carpeta `inzain/` y **no** debe importar de
  `sentinel_omega/` ni al revés.
- No pushear a `main` sin permiso explícito. PRs como **draft**.

## Notas de plataforma

- `winsound` (sonidos) solo existe en Windows; en Linux/macOS se deshabilita solo.
- `QtWebEngine` requiere entorno gráfico: no se puede hacer smoke-test de la GUI en
  CI headless. Los tests de CI cubren la lógica pura (`urls`, `config`).
