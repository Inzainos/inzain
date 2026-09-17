# logging_setup.py
"""
Logging para InZain. SIEMPRE escribe a archivo rotativo y a consola.

Regla del capitán: "Siempre que se generen programas, generar logs."
Aquí se cumple de forma incondicional. Sin secretos en los logs.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

import config

_CONFIGURED = False


def setup_logging() -> logging.Logger:
    """Configura el logger raíz 'InZain'. Idempotente."""
    global _CONFIGURED
    root = logging.getLogger("InZain")
    if _CONFIGURED:
        return root

    os.makedirs(config.LOG_DIR, exist_ok=True)
    log_path = os.path.join(config.LOG_DIR, config.LOG_FILE)

    level = getattr(logging, config.LOG_LEVEL, logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root.setLevel(level)
    root.propagate = False  # no duplicar hacia el root global de Python

    if not root.handlers:  # evita handlers duplicados si se llama dos veces
        fh = RotatingFileHandler(
            log_path,
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=config.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        fh.setLevel(level)
        root.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        ch.setLevel(level)
        root.addHandler(ch)

    _CONFIGURED = True
    root.info("Logging inicializado → %s (nivel %s)", log_path, config.LOG_LEVEL)
    return root
