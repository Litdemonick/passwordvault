# password_vault/events.py

from typing import Callable, List, Any, Dict

class Signal:
    """Señal simple tipo pub/sub."""
    def __init__(self):
        self._subs: List[Callable[..., None]] = []

    def connect(self, fn: Callable[..., None]) -> Callable[..., None]:
        self._subs.append(fn)
        return fn

    def emit(self, *args: Any, **kwargs: Dict[str, Any]) -> None:
        # Copia para evitar problemas si alguien desconecta durante el loop
        for fn in list(self._subs):
            try:
                fn(*args, **kwargs)
            except Exception:
                # Evitar que una excepción en un suscriptor rompa a los demás
                pass

class VaultEvents:
    """Colección de señales del dominio."""
    def __init__(self):
        self.entry_changed = Signal()   # add, edit, delete, import

vault_events = VaultEvents()
