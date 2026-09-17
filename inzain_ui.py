# inzain_ui.py
"""
Capa de presentación de InZain / Fractal Core: ventana principal, HUD de
telemetría (normal ↔ mini), barra de herramientas, árbol fractal de pestañas
y splash screen. Tema cyberpunk (verde/negro monoespaciado).

Esta capa NO contiene lógica de navegación: solo construye widgets y expone
métodos (`add_node`, `remove_node`). El cableado vive en main.py (AppController).
"""

import logging

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QTreeWidget, QTreeWidgetItem, QSplitter, QStackedWidget,
    QLineEdit, QPushButton, QFrame, QProgressBar, QStatusBar,
    QSplashScreen, QLabel, QGroupBox,
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

import config

log = logging.getLogger("InZain.UI")

APP_TITLE = config.APP_TITLE
WINDOW_W = config.WINDOW_W
WINDOW_H = config.WINDOW_H
HUD_H_NORMAL = config.HUD_H_NORMAL
SIDEBAR_W = config.SIDEBAR_W

# ─── HOJA DE ESTILOS MAESTRA (CYBERPUNK THEME) ───────────────────────────────

GLOBAL_STYLES = """
    QMainWindow, QWidget {
        background-color: #050505;
        color: #e0e0e0;
        font-family: 'Consolas', 'Courier New', monospace;
    }
    QScrollBar:vertical { border: none; background: #0a0a0a; width: 10px; margin: 0px; }
    QScrollBar::handle:vertical { background: #333; min-height: 20px; border-radius: 5px; }
    QScrollBar::handle:vertical:hover { background: #00FF00; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QScrollBar:horizontal { border: none; background: #0a0a0a; height: 10px; margin: 0px; }
    QScrollBar::handle:horizontal { background: #333; min-width: 20px; border-radius: 5px; }
    QScrollBar::handle:horizontal:hover { background: #00FF00; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }

    QTreeWidget { background-color: #080808; border: none; font-size: 13px; outline: none; }
    QTreeWidget::item { padding: 4px; border-bottom: 1px solid #111; }
    QTreeWidget::item:hover { background-color: #111; color: #fff; }
    QTreeWidget::item:selected {
        background-color: #1a1a1a; color: #00FF00; border-left: 3px solid #00FF00;
    }

    QPushButton {
        background-color: #111; color: #aaa;
        border: 1px solid #333; border-radius: 4px;
        font-weight: bold; font-size: 14px;
    }
    QPushButton:hover { background-color: #222; color: #fff; border-color: #555; }
    QPushButton:pressed { background-color: #00FF00; color: #000; }

    QLineEdit {
        background-color: #000; color: #00FF00;
        border: 1px solid #333; border-radius: 4px; padding: 5px;
        selection-background-color: #00FF00; selection-color: #000;
    }
    QLineEdit:focus { border: 1px solid #00FF00; }

    QStatusBar { background: #0a0a0a; color: #555; border-top: 1px solid #222; }
    QSplitter::handle { background: #222; }
    QSplitter::handle:hover { background: #00FF00; }

    QToolTip {
        background-color: #111; color: #00FF00;
        border: 1px solid #333; padding: 4px;
        font-family: 'Consolas', monospace; font-size: 11px;
    }
"""


# ─── SPLASH SCREEN ───────────────────────────────────────────────────────────

class SplashScreen(QSplashScreen):
    """Pantalla de carga con barra de progreso animada."""

    def __init__(self, pixmap: QPixmap) -> None:
        super().__init__(pixmap)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        bar_h = 8
        self.progress = QProgressBar(self)
        self.progress.setGeometry(
            50, max(0, pixmap.height() - bar_h - 20),
            max(1, pixmap.width() - 100), bar_h,
        )
        self.progress.setStyleSheet(
            "QProgressBar { border: none; background: #111; border-radius: 4px; }"
            "QProgressBar::chunk { background-color: #00FF00; border-radius: 4px; }"
        )
        self.progress.setTextVisible(False)

    def update_progress(self, value: int) -> None:
        self.progress.setValue(value)


# ─── VENTANA PRINCIPAL ───────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """Ventana principal del navegador Fractal Core con layout cyberpunk."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(WINDOW_W, WINDOW_H)
        self.setStyleSheet(GLOBAL_STYLES)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(2)

        # ── PANEL IZQUIERDO ──────────────────────────────────────────────────
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(20)
        self.tree.setAnimated(True)
        self.tree.setUniformRowHeights(True)
        left_layout.addWidget(self.tree)

        self.hud_stack = QStackedWidget()
        self.hud_stack.setFixedHeight(HUD_H_NORMAL)
        self.hud_stack.addWidget(self._build_hud_normal())
        self.hud_stack.addWidget(self._build_hud_mini())
        left_layout.addWidget(self.hud_stack)

        self.splitter.addWidget(self.left_panel)

        # ── PANEL DERECHO ────────────────────────────────────────────────────
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        right_layout.addWidget(self._build_toolbar())

        self.stack = QStackedWidget()
        right_layout.addWidget(self.stack)

        self.splitter.addWidget(right_panel)
        self.splitter.setSizes([SIDEBAR_W, WINDOW_W - SIDEBAR_W])
        main_layout.addWidget(self.splitter)

        # ── STATUS BAR + PROGRESO ────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(150)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: none; background: #111; border-radius: 2px; }"
            "QProgressBar::chunk { background-color: #0f0; }"
        )
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)

        log.debug("MainWindow construida.")

    # ── BUILDERS INTERNOS ────────────────────────────────────────────────────

    @staticmethod
    def _make_cyber_bar(label_text: str, color: str):
        """Widget de métrica con etiqueta y barra de progreso ultrafina."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        lbl = QLabel(label_text)
        bar = QProgressBar()
        bar.setFixedHeight(4)
        bar.setTextVisible(False)
        bar.setStyleSheet(
            f"QProgressBar {{ border: none; background: #1a1a1a; border-radius: 2px; }}"
            f"QProgressBar::chunk {{ background-color: {color}; border-radius: 2px; }}"
        )
        layout.addWidget(lbl)
        layout.addWidget(bar)
        return container, lbl, bar

    def _build_hud_normal(self) -> QGroupBox:
        """Vista HUD de texto (modo normal)."""
        box = QGroupBox("SYSTEM VITALS")
        box.setStyleSheet("""
            QGroupBox {
                border-top: 1px solid #222; margin-top: 0px;
                border-radius: 0px; background: #080808;
            }
            QGroupBox::title {
                color: #444; font-size: 9px;
                subcontrol-origin: margin; left: 10px; top: 5px;
            }
            QLabel { font-size: 10px; color: #888; margin-bottom: 1px; font-weight: bold; }
        """)
        layout = QVBoxLayout(box)
        layout.setSpacing(6)
        layout.setContentsMargins(15, 25, 15, 10)

        self.cont_cpu, self.lbl_cpu_title, self.prog_cpu = self._make_cyber_bar("CPU_LOAD", "#00FF00")
        self.cont_ram, self.lbl_ram_title, self.prog_ram = self._make_cyber_bar("MEM_USAGE", "#FF00FF")
        self.cont_net, self.lbl_net_title, self.prog_net = self._make_cyber_bar("NET_TRAFFIC", "#00FFFF")

        layout.addWidget(self.cont_cpu)
        layout.addWidget(self.cont_ram)
        layout.addWidget(self.cont_net)
        return box

    def _build_hud_mini(self) -> QWidget:
        """Vista HUD de barras verticales (modo mini)."""
        widget = QWidget()
        widget.setStyleSheet("background: #050505; border-right: 1px solid #222;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(6)

        def vbar(color: str, tip: str) -> QProgressBar:
            p = QProgressBar()
            p.setOrientation(Qt.Orientation.Vertical)
            p.setRange(0, 100)
            p.setTextVisible(False)
            p.setToolTip(tip)
            p.setStyleSheet(
                f"QProgressBar {{ border: 1px solid #222; background: #111; border-radius: 3px; }}"
                f"QProgressBar::chunk {{ background-color: {color}; border-radius: 2px; }}"
            )
            return p

        self.bar_cpu = vbar("#00FF00", "CPU")
        self.bar_ram = vbar("#FF00FF", "RAM")
        self.bar_net = vbar("#00FFFF", "NET")

        layout.addWidget(self.bar_cpu)
        layout.addWidget(self.bar_ram)
        layout.addWidget(self.bar_net)
        return widget

    def _build_toolbar(self) -> QWidget:
        """Barra de herramientas: navegación + URL bar + acciones."""
        container = QWidget()
        container.setStyleSheet("background: #0a0a0a; border-bottom: 1px solid #222;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(5, 6, 5, 6)
        layout.setSpacing(6)

        def btn(label: str, size: int = 32, tip: str = "") -> QPushButton:
            b = QPushButton(label)
            b.setFixedSize(size, size)
            if tip:
                b.setToolTip(tip)
            return b

        def divider() -> QFrame:
            f = QFrame()
            f.setFrameShape(QFrame.Shape.VLine)
            f.setFixedWidth(1)
            f.setStyleSheet("background: #333;")
            return f

        self.btn_sidebar = btn("\u2630", tip="Colapsar/Expandir panel (Ctrl+B)")
        layout.addWidget(self.btn_sidebar)
        layout.addWidget(divider())

        self.btn_back = btn("\u2039", tip="Atrás")
        self.btn_forward = btn("\u203a", tip="Adelante")
        self.btn_reload = btn("\u27f3", tip="Recargar (F5)")
        layout.addWidget(self.btn_back)
        layout.addWidget(self.btn_forward)
        layout.addWidget(self.btn_reload)
        layout.addWidget(divider())

        self.btn_new = btn("+", tip="Nueva pestaña (Ctrl+T)")
        self.btn_new.setStyleSheet(
            "QPushButton { color: #0f0; border: 1px solid #333; }"
            "QPushButton:hover { border-color: #0f0; background: #002200; }"
        )
        self.btn_del = btn("\u00d7", tip="Cerrar pestaña (Ctrl+W)")
        self.btn_del.setStyleSheet(
            "QPushButton { color: #f00; border: 1px solid #333; }"
            "QPushButton:hover { border-color: #f00; background: #220000; }"
        )
        layout.addWidget(self.btn_new)
        layout.addWidget(self.btn_del)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText(">> SYSTEM READY...")
        self.url_bar.setFixedHeight(32)
        layout.addWidget(self.url_bar)

        self.btn_speak = btn("\U0001f5e3", tip="Leer página en voz alta")
        self.btn_speak.setStyleSheet(
            "QPushButton { color: #0ff; } QPushButton:hover { border-color: #0ff; background: #002222; }"
        )
        self.btn_clean = btn("\U0001f9f9", tip="Purgar anuncios y distracciones")
        self.btn_clean.setStyleSheet(
            "QPushButton { color: #fc0; } QPushButton:hover { border-color: #fc0; background: #221a00; }"
        )
        layout.addWidget(self.btn_speak)
        layout.addWidget(self.btn_clean)

        return container

    # ── ÁRBOL FRACTAL ────────────────────────────────────────────────────────

    def add_node(self, title: str, parent: QTreeWidgetItem = None) -> QTreeWidgetItem:
        """Agrega un nodo al árbol fractal (raíz o hijo)."""
        item = QTreeWidgetItem(parent) if parent else QTreeWidgetItem(self.tree)
        item.setText(0, title)
        if parent:
            parent.setExpanded(True)
        return item

    def remove_node(self, item: QTreeWidgetItem) -> None:
        """Elimina un nodo (y destruye su browser asociado) del árbol fractal."""
        browser = item.data(0, Qt.ItemDataRole.UserRole)
        if browser is not None:
            for i in range(self.stack.count()):
                if self.stack.widget(i) is browser:
                    self.stack.removeWidget(browser)
                    browser.deleteLater()
                    break

        parent = item.parent()
        if parent is not None:
            parent.removeChild(item)
        else:
            idx = self.tree.indexOfTopLevelItem(item)
            if idx >= 0:
                self.tree.takeTopLevelItem(idx)
        log.debug("Nodo eliminado del árbol.")
