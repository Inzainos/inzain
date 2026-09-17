# config.py
"""
Configuración central de InZain / Fractal Core.

Todos los flags peligrosos viven aquí, son EXPLÍCITOS y auditables, y pueden
sobreescribirse por variable de entorno (prefijo INZAIN_). Esto respeta la
regla del repo: "secretos y comportamiento sensible solo por entorno".

Defaults elegidos con criterio de seguridad: lo que puede exponerte
(ignorar TLS, conceder cámara/mic sin preguntar) viene APAGADO por defecto.
"""

import os


def _env_bool(name: str, default: bool) -> bool:
    """Lee un booleano desde entorno. Acepta 1/true/yes/on/si/sí."""
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on", "si", "sí")


# ─── IDENTIDAD / VENTANA ──────────────────────────────────────────────────────
APP_NAME = "Fractal Core"
APP_TITLE = "InZain — Fractal Core v11"
HOME_URL = os.environ.get("INZAIN_HOME_URL", "https://duckduckgo.com")
# {query} se rellena ya URL-encoded.
SEARCH_URL = os.environ.get("INZAIN_SEARCH_URL", "https://duckduckgo.com/?q={query}")

WINDOW_W = 1280
WINDOW_H = 800
SIDEBAR_W = 220
HUD_H_NORMAL = 130

# ─── SEGURIDAD (defaults SEGUROS; actívalos bajo tu propio riesgo) ────────────
# Aceptar certificados TLS inválidos. Útil SOLO en redes locales / desarrollo.
# Por defecto False: un navegador NO debe ignorar TLS por defecto (riesgo MITM).
ACCEPT_INVALID_CERTS = _env_bool("INZAIN_ACCEPT_INVALID_CERTS", False)

# Escudo de red: bloqueo de trackers/ads a nivel de request (antes venía
# comentado en el código; ahora es un flag real). Encendido por defecto.
ENABLE_SHIELD = _env_bool("INZAIN_ENABLE_SHIELD", True)

# Conceder automáticamente permisos de medios (mic/cámara/captura de pantalla).
# Apagado por defecto: no queremos que cualquier web tome la cámara sin avisar.
AUTO_GRANT_MEDIA = _env_bool("INZAIN_AUTO_GRANT_MEDIA", False)

# User-Agent anti-detección (imita Chrome). Apagado por defecto.
USE_FAKE_UA = _env_bool("INZAIN_USE_FAKE_UA", False)
FAKE_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Permitir contenido inseguro (http dentro de https). Apagado: es un anti-patrón.
ALLOW_INSECURE_CONTENT = _env_bool("INZAIN_ALLOW_INSECURE_CONTENT", False)

# ─── ESCUDO: DOMINIOS BLOQUEADOS ──────────────────────────────────────────────
SHIELD_BLACKLIST = (
    "doubleclick.net",
    "googlesyndication.com",
    "adservice.google.com",
    "googletagmanager.com",
    "google-analytics.com",
    "facebook.net",
    "connect.facebook.net",
    "analytics.tiktok.com",
    "ads.yahoo.com",
    "scorecardresearch.com",
    "hotjar.com",
    "criteo.com",
)

# ─── VOZ / TTS ────────────────────────────────────────────────────────────────
TTS_RATE = 170
TTS_CHAR_LIMIT = 5000

# ─── TELEMETRÍA ───────────────────────────────────────────────────────────────
TELEMETRY_INTERVAL_MS = 1000

# ─── LOGGING (siempre activo: archivo rotativo + consola) ─────────────────────
LOG_DIR = os.environ.get("INZAIN_LOG_DIR", "logs")
LOG_FILE = "inzain.log"
LOG_LEVEL = os.environ.get("INZAIN_LOG_LEVEL", "INFO").upper()
LOG_MAX_BYTES = 2 * 1024 * 1024   # 2 MB por archivo
LOG_BACKUP_COUNT = 5
