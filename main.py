# main.py
"""
Punto de entrada de InZain / Fractal Core.

Orquesta la UI (inzain_ui) y el núcleo (inzain_core) mediante AppController.
Inicializa el logging ANTES que nada (regla: siempre generar logs).
"""

import signal
import sys
import os
import time

# El logging debe quedar listo antes de crear cualquier objeto que loggee.
from logging_setup import setup_logging
log = setup_logging()

from PyQt6.QtWidgets import QApplication, QFileDialog
from PyQt6.QtGui import QIcon, QPixmap, QKeySequence, QShortcut
from PyQt6.QtCore import QUrl, QTimer, Qt

import config
import psutil

from inzain_core import (
    InzainWebEngine, SessionManager, play_sound, VoiceEngine, PURGE_SCRIPT,
)
from urls import resolve_url
from inzain_ui import MainWindow, SplashScreen


def resource_path(relative_path: str) -> str:
    """Resuelve rutas absolutas compatible con PyInstaller y modo desarrollo."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


class AppController:
    """Controlador principal del navegador InZain / Fractal Core."""

    def __init__(self) -> None:
        # Anti-bot flag (debe ir ANTES de crear QApplication)
        if "--disable-blink-features=AutomationControlled" not in sys.argv:
            sys.argv.append("--disable-blink-features=AutomationControlled")

        self.app = QApplication(sys.argv)
        self.app.setApplicationName(config.APP_NAME)
        log.info("Arranque de %s.", config.APP_NAME)

        self._show_splash()
        self._init_core()
        self._connect_signals()
        self._start_telemetry()
        self._install_signal_handlers()
        self._restore_or_open_default()
        self._finalize()

    # ─── INICIALIZACIÓN ──────────────────────────────────────────────────────

    def _show_splash(self) -> None:
        """Muestra el splash screen con barra de progreso animada (si hay imagen)."""
        self.splash = None
        try:
            pixmap = QPixmap(resource_path("assets/splash_fractal_core.png"))
            if pixmap.isNull():
                log.info("Splash no encontrado — se omite la pantalla de carga.")
                return
            self.splash = SplashScreen(pixmap)
            self.splash.show()
            for i in range(1, 101):
                self.splash.update_progress(i)
                QApplication.processEvents()
                time.sleep(0.005 if i < 80 else 0.02)  # efecto cinético
        except Exception as e:  # noqa: BLE001
            log.warning("Splash screen no disponible: %s", e)
            self.splash = None

    def _init_core(self) -> None:
        """Inicializa los componentes principales."""
        play_sound("startup")
        self.voice_bot = VoiceEngine()
        self.window = MainWindow()

        icon = QIcon(resource_path("assets/fractal.ico"))
        if not icon.isNull():
            self.window.setWindowIcon(icon)
        else:
            log.info("Icono fractal.ico no encontrado — se usa el icono por defecto.")

    def _connect_signals(self) -> None:
        """Conecta todos los eventos UI → controlador."""
        w = self.window

        w.btn_sidebar.clicked.connect(self.toggle_sidebar)
        w.btn_back.clicked.connect(self.nav_back)
        w.btn_forward.clicked.connect(self.nav_forward)
        w.btn_reload.clicked.connect(self.nav_reload)
        w.btn_new.clicked.connect(lambda: self.add_tab(config.HOME_URL))
        w.btn_del.clicked.connect(self.remove_current_tab)
        w.btn_speak.clicked.connect(self.read_current_page)
        w.btn_clean.clicked.connect(self.clean_current_page)
        w.url_bar.returnPressed.connect(self.navigate)
        w.tree.currentItemChanged.connect(self.switch_tab)

        # Atajos de teclado
        QShortcut(QKeySequence("Ctrl+B"), w).activated.connect(self.toggle_sidebar)
        QShortcut(QKeySequence("Ctrl++"), w).activated.connect(self.zoom_in)
        QShortcut(QKeySequence("Ctrl+="), w).activated.connect(self.zoom_in)  # sin Shift
        QShortcut(QKeySequence("Ctrl+-"), w).activated.connect(self.zoom_out)
        QShortcut(QKeySequence("Ctrl+T"), w).activated.connect(lambda: self.add_tab(config.HOME_URL))
        QShortcut(QKeySequence("Ctrl+W"), w).activated.connect(self.remove_current_tab)
        QShortcut(QKeySequence("F5"), w).activated.connect(self.nav_reload)

    def _start_telemetry(self) -> None:
        """Inicializa el timer de telemetría del sistema."""
        self.last_net_io = psutil.net_io_counters()
        self.timer_stats = QTimer()
        self.timer_stats.timeout.connect(self.update_system_stats)
        self.timer_stats.start(config.TELEMETRY_INTERVAL_MS)

    def _install_signal_handlers(self) -> None:
        """Cierra ordenadamente ante SIGTERM/SIGINT para no perder la sesión.

        `_on_quit` cuelga de `aboutToQuit`, que Qt NO dispara cuando el proceso
        recibe una señal: el bucle de eventos muere en C++ sin avisar y el
        árbol de pestañas se pierde. Ocurre en un `kill`, al cerrar sesión el
        sistema operativo o al apagar la máquina.

        Dos piezas hacen falta:
          1. Traducir la señal en `app.quit()`, que sí emite `aboutToQuit`.
          2. Un temporizador que devuelva el control al intérprete de Python
             cada tanto. Sin él, Qt bloquea dentro de C++ y el manejador de
             Python no llega a ejecutarse hasta el siguiente evento de la UI
             --- que en un cierre desatendido puede no llegar nunca.
        """
        def _al_recibir_senal(numero, _frame):
            log.info("Señal %s recibida — cierre ordenado.",
                     signal.Signals(numero).name)
            self.app.quit()

        for s in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(s, _al_recibir_senal)
            except (ValueError, OSError) as e:  # p.ej. fuera del hilo principal
                log.warning("No se pudo instalar el manejador de %s: %s", s, e)

        # Late al intérprete para que las señales se procesen aunque la UI
        # esté quieta. 200 ms es imperceptible y su costo es nulo.
        self._timer_senales = QTimer()
        self._timer_senales.timeout.connect(lambda: None)
        self._timer_senales.start(200)

    def _restore_or_open_default(self) -> None:
        """Restaura la sesión previa o abre la home como pestaña inicial."""
        session_data = SessionManager.load_session()
        if session_data:
            self.restore_session(session_data)
        else:
            self.add_tab(config.HOME_URL, "Nexus")

    def _finalize(self) -> None:
        """Muestra la ventana y conecta el guardado de sesión al cierre."""
        if self.splash:
            self.splash.finish(self.window)
        self.window.show()
        self.app.aboutToQuit.connect(self._on_quit)
        log.info("Interfaz lista.")

    def _on_quit(self) -> None:
        """Guarda la sesión y detiene la telemetría de forma ordenada."""
        log.info("Cierre solicitado — guardando sesión.")
        self.timer_stats.stop()
        if hasattr(self, "_timer_senales"):
            self._timer_senales.stop()
        SessionManager.save_session(self.window.tree)

    # ─── SIDEBAR TOGGLE ──────────────────────────────────────────────────────

    def toggle_sidebar(self) -> None:
        """Alterna entre modo normal (árbol) y modo mini (barras verticales)."""
        is_expanded = not self.window.tree.isHidden()
        panel = self.window.left_panel

        if is_expanded:
            self.window.tree.hide()
            self.window.hud_stack.setCurrentIndex(1)
            panel.setMaximumWidth(50)
            self.window.hud_stack.setMaximumHeight(16777215)
        else:
            self.window.tree.show()
            self.window.hud_stack.setCurrentIndex(0)
            panel.setMaximumWidth(16777215)
            self.window.hud_stack.setFixedHeight(config.HUD_H_NORMAL)
            self.window.splitter.setSizes([config.SIDEBAR_W, config.WINDOW_W - config.SIDEBAR_W])

    # ─── TELEMETRÍA ──────────────────────────────────────────────────────────

    def update_system_stats(self) -> None:
        """Actualiza CPU, RAM y RED en ambas vistas del HUD."""
        cpu = psutil.cpu_percent()
        self.window.lbl_cpu_title.setText(f"CPU: {cpu:.0f}%")
        self.window.prog_cpu.setValue(int(cpu))
        self.window.bar_cpu.setValue(int(cpu))

        ram = psutil.virtual_memory().percent
        self.window.lbl_ram_title.setText(f"RAM: {ram:.0f}%")
        self.window.prog_ram.setValue(int(ram))
        self.window.bar_ram.setValue(int(ram))

        net_io = psutil.net_io_counters()
        kb_recv = (net_io.bytes_recv - self.last_net_io.bytes_recv) / 1024
        kb_sent = (net_io.bytes_sent - self.last_net_io.bytes_sent) / 1024
        self.last_net_io = net_io

        self.window.lbl_net_title.setText(f"NET: \u2193{kb_recv:.0f} \u2191{kb_sent:.0f} KB/s")
        net_percent = min(100, int((kb_recv + kb_sent) / 10))
        self.window.prog_net.setValue(net_percent)
        self.window.bar_net.setValue(net_percent)

    # ─── PESTAÑAS ────────────────────────────────────────────────────────────

    def add_tab(self, url: str, title: str = "NEW_NODE", parent_item=None) -> None:
        """Crea una nueva pestaña y la agrega al árbol fractal."""
        play_sound("new_tab")
        browser = InzainWebEngine()
        browser.setUrl(QUrl(url))
        browser.titleChanged.connect(lambda t, b=browser: self.update_tab_title(t, b))
        browser.urlChanged.connect(lambda q, b=browser: self.update_url_bar(q, b))
        browser.loadStarted.connect(self.window.progress_bar.show)
        browser.loadProgress.connect(self.window.progress_bar.setValue)
        browser.loadFinished.connect(self.window.progress_bar.hide)
        browser.page().linkHovered.connect(self.show_link_preview)
        browser.page().profile().downloadRequested.connect(self.handle_download)

        self.window.stack.addWidget(browser)

        if not parent_item:
            parent_item = self.window.tree.currentItem()
        item = self.window.add_node(title, parent_item)
        item.setData(0, Qt.ItemDataRole.UserRole, browser)
        self.window.tree.setCurrentItem(item)
        log.info("Nueva pestaña: %s", url)

    def remove_current_tab(self) -> None:
        """Elimina la pestaña activa del árbol fractal."""
        item = self.window.tree.currentItem()
        if item:
            play_sound("threat_voided")
            self.window.remove_node(item)

    def switch_tab(self, current, _previous) -> None:
        """Cambia la vista del stack al browser del nodo seleccionado."""
        if current:
            browser = current.data(0, Qt.ItemDataRole.UserRole)
            if browser:
                self.window.stack.setCurrentWidget(browser)
                self.window.url_bar.setText(browser.url().toString())

    # ─── NAVEGACIÓN ──────────────────────────────────────────────────────────

    def navigate(self) -> None:
        """Navega según el texto de la barra (usa urls.resolve_url)."""
        url = resolve_url(self.window.url_bar.text())
        if not url:
            return
        widget = self._current_browser()
        if widget:
            widget.setUrl(QUrl(url))
            log.debug("Navegando a %s", url)

    def _current_browser(self):
        return self.window.stack.currentWidget()

    def nav_back(self) -> None:
        if w := self._current_browser():
            w.back()

    def nav_forward(self) -> None:
        if w := self._current_browser():
            w.forward()

    def nav_reload(self) -> None:
        if w := self._current_browser():
            w.reload()

    # ─── VOZ Y LIMPIEZA ──────────────────────────────────────────────────────

    def read_current_page(self) -> None:
        """Alterna la lectura en voz alta del contenido de la página actual."""
        b = self._current_browser()
        if not b:
            return
        if self.voice_bot.engine and self.voice_bot.engine.isBusy():
            self.voice_bot.stop()
        else:
            b.page().toPlainText(
                lambda t: self.voice_bot.speak(t[:config.TTS_CHAR_LIMIT])
            )

    def clean_current_page(self) -> None:
        """Ejecuta el script de purga anti-anuncios en la página actual."""
        b = self._current_browser()
        if b:
            b.page().runJavaScript(PURGE_SCRIPT)
            play_sound("purge")
            log.info("Purga visual ejecutada.")

    # ─── ZOOM ────────────────────────────────────────────────────────────────

    def zoom_in(self) -> None:
        if b := self._current_browser():
            b.setZoomFactor(min(b.zoomFactor() + 0.1, 5.0))

    def zoom_out(self) -> None:
        if b := self._current_browser():
            b.setZoomFactor(max(b.zoomFactor() - 0.1, 0.25))

    # ─── ÁRBOL FRACTAL ───────────────────────────────────────────────────────

    def update_tab_title(self, title: str, browser) -> None:
        """Actualiza el título del nodo correspondiente al browser dado."""
        root = self.window.tree.invisibleRootItem()

        def find_item(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole) is browser:
                    return child
                found = find_item(child)
                if found:
                    return found
            return None

        item = find_item(root)
        if item:
            display = title[:25] + "\u2026" if len(title) > 25 else title
            item.setText(0, display)

    def update_url_bar(self, qurl, browser) -> None:
        """Actualiza la barra de URL solo si el browser activo cambió de dirección."""
        if browser is self.window.stack.currentWidget():
            self.window.url_bar.setText(qurl.toString())

    def show_link_preview(self, url: str) -> None:
        """Muestra la URL de un enlace en la barra de estado al pasar el cursor."""
        self.window.status_bar.showMessage(url)

    # ─── DESCARGAS ───────────────────────────────────────────────────────────

    def handle_download(self, download) -> None:
        """Gestiona las descargas solicitadas por el motor web."""
        path, _ = QFileDialog.getSaveFileName(
            self.window, "Guardar archivo", download.suggestedFileName()
        )
        if path:
            download.setPath(path)
            download.accept()
            download.finished.connect(lambda: play_sound("load_complete"))
            log.info("Descarga aceptada: %s", path)
        else:
            download.cancel()
            log.info("Descarga cancelada por el usuario.")

    # ─── SESIÓN ──────────────────────────────────────────────────────────────

    def restore_session(self, data: list, parent_item=None) -> None:
        """Restaura recursivamente el árbol de pestañas desde los datos de sesión."""
        for node in data:
            self.add_tab(node["url"], node.get("title", "NODE"), parent_item)
            current = self.window.tree.currentItem()
            if node.get("children"):
                self.restore_session(node["children"], current)


if __name__ == "__main__":
    try:
        controller = AppController()
        sys.exit(controller.app.exec())
    except Exception:
        log.exception("Fallo fatal en el arranque de InZain.")
        raise
