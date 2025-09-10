# password_vault/export_import.py
# Exporta/Importa entradas del vault a un blob binario (zlib+json)
# Compatible con tu flujo actual: export_vault_to_blob(SessionLocal, key) / import_vault_from_blob(SessionLocal, key, blob)

import json
import base64
import zlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from password_vault.db import SessionLocal, Entry  # absoluto

def _has_col(name: str) -> bool:
    return name in Entry.__table__.c.keys()

def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")

def _b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))

def export_vault_to_blob(session_factory, key: bytes) -> bytes:
    """
    Exporta todas las filas de 'entries' a un blob comprimido (zlib) en JSON.
    No re-cifra nada adicional (las contraseñas ya están en password_encrypted).
    """
    with session_factory() as s:
        rows = s.query(Entry).all()

    has_email   = _has_col("email")
    has_created = _has_col("created_at")
    has_updated = _has_col("updated_at")
    has_fav     = _has_col("is_favorite")
    has_deleted = _has_col("deleted_at")

    out: List[Dict[str, Any]] = []
    for e in rows:
        d: Dict[str, Any] = {
            "title": e.title,
            "username": e.username,
            "url": e.url,
            "notes": e.notes,
            "password_encrypted": _b64e(e.password_encrypted),
        }
        if has_email:
            d["email"] = getattr(e, "email", None)
        if has_created:
            ca = getattr(e, "created_at", None)
            d["created_at"] = ca.isoformat() if ca else None
        if has_updated:
            ua = getattr(e, "updated_at", None)
            d["updated_at"] = ua.isoformat() if ua else None
        if has_fav:
            d["is_favorite"] = bool(getattr(e, "is_favorite", False))
        if has_deleted:
            da = getattr(e, "deleted_at", None)
            d["deleted_at"] = da.isoformat() if da else None
        out.append(d)

    pkg = {
        "kind": "passwordvault-entries",
        "version": 1,
        "exported": datetime.utcnow().isoformat() + "Z",
        "entries": out,
    }
    data = json.dumps(pkg, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return zlib.compress(data)

def import_vault_from_blob(session_factory, key: bytes, blob: bytes) -> int:
    """
    Importa un blob (zlib+json) y crea nuevas filas en 'entries'.
    Devuelve la cantidad de entradas insertadas.
    """
    # zlib → json (fallback sin compresión)
    try:
        data = zlib.decompress(blob)
    except Exception:
        data = blob

    pkg = json.loads(data.decode("utf-8", errors="replace"))
    items = pkg.get("entries", [])

    has_email   = _has_col("email")
    has_fav     = _has_col("is_favorite")
    has_deleted = _has_col("deleted_at")

    def _merge_notes_with_email(notes: Optional[str], email: Optional[str]) -> str:
        notes = (notes or "").strip()
        if email and "email:" not in notes.lower():
            extra = f"\nEmail: {email}" if notes else f"Email: {email}"
            return (notes + extra).strip()
        return notes

    inserted = 0
    with session_factory() as s:
        for d in items:
            e = Entry(
                title=d.get("title"),
                username=d.get("username"),
                url=d.get("url"),
                notes=d.get("notes"),
                password_encrypted=_b64d(d["password_encrypted"]),
            )
            # Email: columna si existe, o se añade a notas
            email_val = d.get("email")
            if has_email:
                setattr(e, "email", email_val)
            else:
                e.notes = _merge_notes_with_email(e.notes, email_val)

            # Flags extra
            if has_fav and "is_favorite" in d:
                setattr(e, "is_favorite", bool(d.get("is_favorite")))
            if has_deleted and d.get("deleted_at"):
                try:
                    setattr(e, "deleted_at", datetime.fromisoformat(d["deleted_at"].replace("Z", "")))
                except Exception:
                    pass

            s.add(e)
            inserted += 1

        s.commit()
    return inserted
