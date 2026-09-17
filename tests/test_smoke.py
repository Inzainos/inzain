"""
Tests headless de InZain (no requieren GUI ni PyQt6).

Cubren la lógica pura extraída del navegador: resolución de URL, flags de
configuración y el script de purga. Ejecutar desde la raíz del proyecto:

    python -m pytest tests/ -q
"""

import config
from urls import resolve_url


# ─── resolve_url ──────────────────────────────────────────────────────────────

def test_vacio_devuelve_none():
    assert resolve_url("") is None
    assert resolve_url("   ") is None
    assert resolve_url(None) is None


def test_https_explicito_se_respeta():
    assert resolve_url("https://example.com") == "https://example.com"
    assert resolve_url("http://example.com") == "http://example.com"


def test_localhost_usa_http():
    assert resolve_url("localhost:8080") == "http://localhost:8080"
    assert resolve_url("127.0.0.1:5000") == "http://127.0.0.1:5000"
    assert resolve_url("192.168.1.10") == "http://192.168.1.10"


def test_dominio_pelado_recibe_https():
    assert resolve_url("example.com") == "https://example.com"
    assert resolve_url("duckduckgo.com/foo") == "https://duckduckgo.com/foo"


def test_texto_con_espacios_es_busqueda():
    out = resolve_url("teoría del fungiverso")
    assert out.startswith("https://duckduckgo.com/?q=")
    # el espacio debe ir URL-encoded, nunca crudo
    assert " " not in out


def test_palabra_sin_punto_es_busqueda():
    out = resolve_url("python")
    assert out.startswith("https://duckduckgo.com/?q=")


# ─── config ───────────────────────────────────────────────────────────────────

def test_flags_de_seguridad_son_seguros_por_defecto():
    # Lo peligroso viene apagado
    assert config.ACCEPT_INVALID_CERTS is False
    assert config.AUTO_GRANT_MEDIA is False
    assert config.USE_FAKE_UA is False
    assert config.ALLOW_INSECURE_CONTENT is False
    # El escudo viene encendido
    assert config.ENABLE_SHIELD is True


def test_blacklist_es_tupla_de_strings_no_vacia():
    assert isinstance(config.SHIELD_BLACKLIST, tuple)
    assert len(config.SHIELD_BLACKLIST) > 0
    assert all(isinstance(d, str) and d for d in config.SHIELD_BLACKLIST)


def test_env_bool_interpreta_valores(monkeypatch):
    monkeypatch.setenv("INZAIN_TEST_FLAG", "true")
    assert config._env_bool("INZAIN_TEST_FLAG", False) is True
    monkeypatch.setenv("INZAIN_TEST_FLAG", "0")
    assert config._env_bool("INZAIN_TEST_FLAG", True) is False
    monkeypatch.delenv("INZAIN_TEST_FLAG", raising=False)
    assert config._env_bool("INZAIN_TEST_FLAG", True) is True


# ─── purge script ─────────────────────────────────────────────────────────────

def test_purge_script_definido():
    # Solo corre si PyQt6 está instalado (inzain_core lo importa al cargar).
    import pytest
    pytest.importorskip("PyQt6", reason="PyQt6 no instalado en este entorno")
    import importlib
    core = importlib.import_module("inzain_core")
    assert isinstance(core.PURGE_SCRIPT, str)
    assert "querySelectorAll" in core.PURGE_SCRIPT
