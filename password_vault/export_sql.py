# password_vault/export_sql.py
import base64
from datetime import datetime
from typing import Optional
from .db import SessionLocal, Entry, Setting

def _esc(val):
    if val is None:
        return "NULL"
    if isinstance(val, (bytes, bytearray)):
        b64 = base64.b64encode(val).decode("ascii")
        return f"FROM_BASE64('{b64}')"
    if isinstance(val, datetime):
        return f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'"
    s = str(val).replace("\\", "\\\\").replace("'", "''")
    return f"'{s}'"

def _col_exists(name: str) -> bool:
    return name in Entry.__table__.c.keys()

def build_sql_dump_string(session_factory) -> str:
    """Devuelve un dump SQL (DDL + INSERTs) como string."""
    has_created = _col_exists("created_at")
    has_updated = _col_exists("updated_at")
    has_fav     = _col_exists("is_favorite")
    has_deleted = _col_exists("deleted_at")
    has_email   = _col_exists("email")  # si existiera en tu modelo

    with session_factory() as s:
        settings = s.query(Setting).all()
        entries  = s.query(Entry).all()

    lines: list[str] = []
    lines.append("-- PasswordVault SQL dump (pmvault bundle)")
    lines.append("")

    lines += [
        "CREATE TABLE IF NOT EXISTS settings (",
        "  id INT PRIMARY KEY AUTO_INCREMENT,",
        "  kdf_salt BLOB NOT NULL,",
        "  verifier BLOB NOT NULL",
        ");",
        "",
        "CREATE TABLE IF NOT EXISTS entries (",
        "  id INT PRIMARY KEY AUTO_INCREMENT,",
        "  title VARCHAR(255),",
        "  username VARCHAR(255),",
        "  url VARCHAR(512),",
        "  notes TEXT,",
        "  password_encrypted LONGBLOB NOT NULL," +
        ("  created_at DATETIME," if has_created else "") +
        ("  updated_at DATETIME," if has_updated else "") +
        ("  email VARCHAR(255)," if has_email else "") +
        ("  is_favorite TINYINT(1) NOT NULL DEFAULT 0," if has_fav else "") +
        ("  deleted_at DATETIME," if has_deleted else ""),
        "  dummy_padding INT NULL",
        ");",
        ""
    ]

    for st in settings:
        lines.append(
            "INSERT INTO settings (id, kdf_salt, verifier) VALUES "
            f"({st.id}, {_esc(st.kdf_salt)}, {_esc(st.verifier)});"
        )

    colnames = ["id", "title", "username", "url", "notes", "password_encrypted"]
    if has_created: colnames.append("created_at")
    if has_updated: colnames.append("updated_at")
    if has_email:   colnames.append("email")
    if has_fav:     colnames.append("is_favorite")
    if has_deleted: colnames.append("deleted_at")

    for e in entries:
        vals = [_esc(getattr(e, c, None)) for c in colnames]
        lines.append(f"INSERT INTO entries ({', '.join(colnames)}) VALUES ({', '.join(vals)});")

    return "\n".join(lines)

def export_sql_dump(session_factory, outfile_path: str) -> None:
    text = build_sql_dump_string(session_factory)
    with open(outfile_path, "w", encoding="utf-8") as fh:
        fh.write(text)
