# urls.py
"""
Resolución del texto de la barra de direcciones a una URL.

Se aísla en su propio módulo (SIN dependencias de Qt) para que la lógica de
navegación sea testeable de forma headless, sin necesidad de arrancar la GUI.
"""

from urllib.parse import quote_plus

import config


def resolve_url(text: str) -> str | None:
    """
    Convierte texto de la barra en una URL navegable.

    Reglas:
      - Vacío                          → None (no navega).
      - Empieza con http:// o https:// → tal cual.
      - localhost / 127.0.0.1 / 192.168.* → HTTP local sin protocolo.
      - Tiene espacios o no tiene punto → búsqueda en el motor configurado.
      - Cualquier otra cosa            → se le antepone https://.
    """
    text = (text or "").strip()
    if not text:
        return None

    if text.startswith(("http://", "https://")):
        return text

    lowered = text.lower()
    if lowered.startswith(("localhost", "127.0.0.1")) or lowered.startswith("192.168."):
        return f"http://{text}"

    if " " in text or "." not in text:
        return config.SEARCH_URL.format(query=quote_plus(text))

    return f"https://{text}"
