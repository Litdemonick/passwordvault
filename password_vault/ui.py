# password_vault/ui.py
import os
from pathlib import Path
import configparser
import ttkbootstrap as tb

# --- Nombre y versión de la app ---
APP_NAME = "PasswordVault"
APP_VERSION = "v1.0.0.0"

# --- Configuración de tema (persistente en archivo .ini) ---
def _user_config_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    p = Path(base) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p

_UI_INI_PATH = _user_config_dir() / "vault_ui.ini"
_UI_INI_SECTION = "ui"
_UI_INI_KEY = "theme"
_DEFAULT_LIGHT = "flatly"
_DEFAULT_DARK = "darkly"

def load_saved_theme(default=_DEFAULT_LIGHT) -> str:
    cfg = configparser.ConfigParser()
    try:
        if _UI_INI_PATH.exists():
            cfg.read(_UI_INI_PATH, encoding="utf-8")
            return cfg.get(_UI_INI_SECTION, _UI_INI_KEY, fallback=default)
    except Exception:
        pass
    return default

def save_theme(theme: str) -> None:
    try:
        _UI_INI_PATH.parent.mkdir(parents=True, exist_ok=True)
        cfg = configparser.ConfigParser()
        if _UI_INI_PATH.exists():
            cfg.read(_UI_INI_PATH, encoding="utf-8")
        if _UI_INI_SECTION not in cfg:
            cfg[_UI_INI_SECTION] = {}
        cfg[_UI_INI_SECTION][_UI_INI_KEY] = theme
        with _UI_INI_PATH.open("w", encoding="utf-8") as f:
            cfg.write(f)
    except Exception:
        pass

# --- Helpers de estilo ---
def apply_style(window, theme=None):
    """
    Aplica el estilo ttkbootstrap al root window.
    """
    theme = theme or load_saved_theme()
    style = tb.Style(theme)
    return style
