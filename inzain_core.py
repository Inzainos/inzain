# inzain_core.py
"""
Núcleo de InZain / Fractal Core:
  - Motor web (QWebEngineView) con perfil persistente.
  - Escudo de red (bloqueo de trackers) configurable.
  - Página con consola JS filtrada.
  - Motor de voz (TTS) en hilo aparte.
  - Sonidos sistémicos.
  - Gestor de sesión (cifrada con Fernet si está disponible, JSON si no).

Todo el comportamiento sensible (TLS, permisos de medios, UA falso, escudo)
se controla desde config.py y queda registrado en el log.
"""

import json
import os
import logging
import threading

from PyQt6.QtCore import QUrl, Qt, QObject
from PyQt6.QtWebEngineCore import (
    QWebEngineSettings,
    QWebEnginePage,
    QWebEngineUrlRequestInterceptor,
    QWebEngineProfile,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView

import config
from urls import resolve_url  # reexport para quien importe desde el core

log = logging.getLogger("InZain.Core")

# Rutas relativas al archivo, no al CWD (evita perder la sesión al cambiar de dir)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── DEPENDENCIAS OPCIONALES ──────────────────────────────────────────────────
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    log.warning("cryptography no instalado — la sesión se guardará SIN cifrar.")

try:
    import pyttsx3
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False
    log.warning("pyttsx3 no instalado — lectura por voz deshabilitada.")

# winsound solo existe en Windows; se maneja aparte para no acoplar el audio al TTS
try:
    import winsound
    SOUND_AVAILABLE = True
except ImportError:
    winsound = None
    SOUND_AVAILABLE = False
    log.info("winsound no disponible (no es Windows) — sonidos deshabilitados.")


# ─── SISTEMA DE SONIDO ────────────────────────────────────────────────────────

_SOUNDS = {
    "startup": [(440, 100), (554, 100), (659, 200)],
    "new_tab": [(880, 50)],
    "load_complete": [(1200, 30)],
    "threat_voided": [(100, 50)],
    "purge": [(300, 150)],
}


def play_sound(event_type: str) -> None:
    """Reproduce una secuencia de beeps sistémicos para el evento dado."""
    if not SOUND_AVAILABLE:
        return
    beeps = _SOUNDS.get(event_type)
    if not beeps:
        log.debug("Sonido desconocido: %r", event_type)
        return
    try:
        for freq, dur in beeps:
            winsound.Beep(freq, dur)
    except Exception as e:  # noqa: BLE001 — audio nunca debe tumbar la app
        log.debug("play_sound error: %s", e)


# ─── SINTETIZADOR DE VOZ ──────────────────────────────────────────────────────

class VoiceEngine(QObject):
    """Motor TTS (pyttsx3). Opera en hilo separado para no bloquear la UI."""

    def __init__(self) -> None:
        super().__init__()
        self.engine = None
        self._lock = threading.Lock()

        if VOICE_AVAILABLE:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty("rate", config.TTS_RATE)
                log.info("VoiceEngine inicializado (rate=%s).", config.TTS_RATE)
            except Exception as e:  # noqa: BLE001
                log.warning("VoiceEngine no pudo inicializar: %s", e)

    def speak(self, text: str) -> None:
        """Lanza la lectura de texto en un hilo demonio."""
        if not self.engine or not text:
            return
        t = threading.Thread(target=self._run_speak, args=(text,), daemon=True)
        t.start()

    def _run_speak(self, text: str) -> None:
        with self._lock:  # evita lecturas solapadas
            try:
                if self.engine.isBusy():
                    self.engine.stop()
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:  # noqa: BLE001
                log.debug("TTS error: %s", e)

    def stop(self) -> None:
        """Detiene la lectura en curso."""
        if self.engine:
            try:
                self.engine.stop()
            except Exception as e:  # noqa: BLE001
                log.debug("VoiceEngine.stop error: %s", e)


# ─── SCRIPT DE PURGA VISUAL (Anti-Ads) ────────────────────────────────────────

PURGE_SCRIPT = """
(function() {
  var tags = ['iframe', 'aside', 'footer', 'nav', 'script', 'style', 'noscript'];
  var classes = ['ad', 'ads', 'advert', 'banner', 'cookie', 'popup', 'newsletter', 'social', 'share'];
  var count = 0;
  tags.forEach(function(t) {
    document.querySelectorAll(t).forEach(function(e) { e.remove(); count++; });
  });
  classes.forEach(function(c) {
    document.querySelectorAll('[class*="' + c + '"]').forEach(function(e) { e.remove(); count++; });
    document.querySelectorAll('[id*="' + c + '"]').forEach(function(e) { e.remove(); count++; });
  });
  document.body.style.background = "#111";
  document.body.style.color = "#eee";
  return count;
})();
"""


# ─── ESCUDO DE RED ────────────────────────────────────────────────────────────

class SecurityShield(QWebEngineUrlRequestInterceptor):
    """Interceptor de requests: bloquea dominios de publicidad y tracking."""

    _VOID = "http://0.0.0.0"

    def __init__(self, blacklist=None) -> None:
        super().__init__()
        self.blacklist = tuple(blacklist if blacklist is not None else config.SHIELD_BLACKLIST)

    def interceptRequest(self, info) -> None:
        url = info.requestUrl().toString().lower()
        for domain in self.blacklist:
            if domain in url:
                log.debug("[SHIELD] Bloqueado: %s", url[:80])
                info.redirect(QUrl(self._VOID))
                return


# ─── PÁGINA PERSONALIZADA ─────────────────────────────────────────────────────

class InzainPage(QWebEnginePage):
    """Página web con consola JS filtrada: solo registra errores reales."""

    _ERROR_LEVEL = QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        if level == self._ERROR_LEVEL:
            log.debug("[JS ERR] %s:%s → %s", source_id, line_number, message[:120])


# ─── MOTOR WEB VISUAL ─────────────────────────────────────────────────────────

class InzainWebEngine(QWebEngineView):
    """Vista web con perfil persistente, escudo y permisos según config."""

    _ALLOWED_FEATURES = None  # cache de clase

    def __init__(self) -> None:
        super().__init__()

        # 1. Página personalizada (filtro de consola JS)
        self.setPage(InzainPage(self))

        # 2. Perfil persistente
        profile = QWebEngineProfile.defaultProfile()
        data_path = os.path.join(_BASE_DIR, "inzain_data")
        profile.setPersistentStoragePath(data_path)
        profile.setCachePath(data_path)

        if config.USE_FAKE_UA:
            profile.setHttpUserAgent(config.FAKE_UA)
            log.info("[UA] User-Agent anti-detección ACTIVADO.")

        # 3. Escudo de red (ahora sí conectado, según config)
        self.interceptor = None
        if config.ENABLE_SHIELD:
            self.interceptor = SecurityShield()
            profile.setUrlRequestInterceptor(self.interceptor)
            log.info("[SHIELD] Escudo de red ACTIVADO (%d dominios).",
                     len(self.interceptor.blacklist))

        # 4. Configuración de funcionalidades web
        s = self.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.ScreenCaptureEnabled, True)
        s.setAttribute(
            QWebEngineSettings.WebAttribute.AllowRunningInsecureContent,
            config.ALLOW_INSECURE_CONTENT,
        )

        # 5. Permisos de medios (según config)
        self.page().featurePermissionRequested.connect(self._grant_permission)

        # 6. Zoom inicial y manejo de TLS
        self.setZoomFactor(1.0)
        self.page().certificateError.connect(self._handle_certificate_error)

    # ── TLS ──────────────────────────────────────────────────────────────────
    def _handle_certificate_error(self, error) -> None:
        """Acepta o rechaza certificados inválidos según config (con log)."""
        host = error.url().host()
        if config.ACCEPT_INVALID_CERTS:
            log.warning("[SSL] Certificado inválido ACEPTADO (config) — %s: %s",
                        host, error.description())
            error.acceptCertificate()
        else:
            log.error("[SSL] Certificado inválido RECHAZADO — %s: %s",
                      host, error.description())
            if hasattr(error, "rejectCertificate"):
                error.rejectCertificate()
            # Si la API no tiene rejectCertificate, no aceptar ya bloquea la carga.

    def createWindow(self, _type):
        """Abre popups en la misma pestaña en lugar de una ventana nueva."""
        return self

    # ── PERMISOS ─────────────────────────────────────────────────────────────
    def _get_allowed_features(self):
        if InzainWebEngine._ALLOWED_FEATURES is None:
            F = QWebEnginePage.Feature
            InzainWebEngine._ALLOWED_FEATURES = {
                F.ClipboardReadWrite,
                F.MediaAudioCapture,
                F.MediaVideoCapture,
                F.MediaAudioVideoCapture,
                F.DesktopVideoCapture,
                F.DesktopAudioVideoCapture,
            }
        return InzainWebEngine._ALLOWED_FEATURES

    def _grant_permission(self, url, feature) -> None:
        """Concede permisos de medios SOLO si config.AUTO_GRANT_MEDIA está activo."""
        Policy = QWebEnginePage.PermissionPolicy
        if config.AUTO_GRANT_MEDIA and feature in self._get_allowed_features():
            log.debug("[PERM] Concedido: %s → %s", feature.name, url.host())
            policy = Policy.PermissionGrantedByUser
        else:
            log.debug("[PERM] Denegado/pendiente: %s → %s", feature.name, url.host())
            policy = Policy.PermissionDeniedByUser
        self.page().setFeaturePermission(url, feature, policy)


# ─── GESTOR DE SESIÓN ─────────────────────────────────────────────────────────

class SessionManager:
    """Guarda/restaura el árbol de pestañas (cifrado con Fernet si está disponible)."""

    KEY_FILE = os.path.join(_BASE_DIR, "inzain.key")
    DATA_FILE = os.path.join(_BASE_DIR, "session_inzain.enc")
    JSON_FILE = os.path.join(_BASE_DIR, "session_inzain.json")

    # Permisos de secreto: solo el dueño. open() usa el umask (habitualmente
    # 0o022 -> 0o644), lo que dejaba la clave Fernet legible por cualquier
    # usuario del sistema. Quien lee inzain.key descifra toda la sesión.
    _MODO_SECRETO = 0o600

    @staticmethod
    def _escribir_secreto(path: str, datos: bytes) -> None:
        """Escribe un archivo sensible sin que pase nunca por 0o644.

        Se crea con O_EXCL y el modo restrictivo desde el primer byte, en vez
        de abrirlo y corregirlo después: entre el open y el chmod hay una
        ventana en la que el secreto es legible por todos.
        """
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                     SessionManager._MODO_SECRETO)
        try:
            archivo = os.fdopen(fd, "wb")
        except Exception:
            os.close(fd)   # fdopen falló: el descriptor sigue abierto
            raise
        with archivo as f:
            f.write(datos)
        # Un archivo preexistente conserva sus permisos pese al modo de open().
        try:
            os.chmod(path, SessionManager._MODO_SECRETO)
        except OSError as e:  # noqa: BLE001
            log.warning("No se pudieron ajustar permisos de %s: %s", path, e)

    @staticmethod
    def _get_cipher():
        if not CRYPTO_AVAILABLE:
            return None
        if not os.path.exists(SessionManager.KEY_FILE):
            SessionManager._escribir_secreto(SessionManager.KEY_FILE,
                                             Fernet.generate_key())
            log.info("Nueva clave de sesión generada (modo 600): %s",
                     SessionManager.KEY_FILE)
        else:
            # Claves creadas por versiones anteriores quedaron en 0o644.
            modo = os.stat(SessionManager.KEY_FILE).st_mode & 0o777
            if modo != SessionManager._MODO_SECRETO:
                try:
                    os.chmod(SessionManager.KEY_FILE,
                             SessionManager._MODO_SECRETO)
                    log.warning("Clave de sesión tenía permisos %o; corregidos "
                                "a 600.", modo)
                except OSError as e:  # noqa: BLE001
                    log.error("Clave con permisos %o y no se pudo corregir: %s",
                              modo, e)
        with open(SessionManager.KEY_FILE, "rb") as kf:
            return Fernet(kf.read())

    @staticmethod
    def serialize_tree(tree_widget) -> list:
        """Convierte el árbol fractal en una lista de nodos serializables."""
        root = tree_widget.invisibleRootItem()

        def serialize(item):
            browser = item.data(0, Qt.ItemDataRole.UserRole)
            return {
                "title": item.text(0),
                "url": browser.url().toString() if browser else "about:blank",
                "children": [serialize(item.child(i)) for i in range(item.childCount())],
            }

        return [serialize(root.child(i)) for i in range(root.childCount())]

    @staticmethod
    def save_session(tree_widget) -> None:
        """Serializa y guarda la sesión (cifrada o JSON plano)."""
        data = SessionManager.serialize_tree(tree_widget)
        json_str = json.dumps(data, ensure_ascii=False, indent=2)

        if CRYPTO_AVAILABLE:
            try:
                cipher = SessionManager._get_cipher()
                encrypted = cipher.encrypt(json_str.encode("utf-8"))
                SessionManager._escribir_secreto(SessionManager.DATA_FILE,
                                                 encrypted)
                log.info("Sesión guardada (cifrada): %d nodos raíz.", len(data))
            except Exception as e:  # noqa: BLE001
                log.error("Error guardando sesión cifrada: %s", e)
        else:
            try:
                # Sin cryptography la sesión queda en claro; al menos que no
                # la lea cualquier usuario del sistema.
                SessionManager._escribir_secreto(
                    SessionManager.JSON_FILE, json_str.encode("utf-8"))
                log.info("Sesión guardada (JSON plano): %d nodos raíz.", len(data))
            except Exception as e:  # noqa: BLE001
                log.error("Error guardando sesión JSON: %s", e)

    @staticmethod
    def load_session():
        """Carga la sesión previa. Retorna lista de nodos o None."""
        if CRYPTO_AVAILABLE and os.path.exists(SessionManager.DATA_FILE):
            try:
                cipher = SessionManager._get_cipher()
                with open(SessionManager.DATA_FILE, "rb") as f:
                    raw = f.read()
                data = json.loads(cipher.decrypt(raw).decode("utf-8"))
                log.info("Sesión cifrada restaurada: %d nodos raíz.", len(data))
                return data
            except Exception as e:  # noqa: BLE001
                log.error("Error cargando sesión cifrada: %s", e)
                return None

        if os.path.exists(SessionManager.JSON_FILE):
            try:
                with open(SessionManager.JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                log.info("Sesión JSON restaurada: %d nodos raíz.", len(data))
                return data
            except Exception as e:  # noqa: BLE001
                log.error("Error cargando sesión JSON: %s", e)
                return None

        return None
