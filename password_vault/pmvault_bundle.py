# password_vault/pmvault_bundle.py
import os, json, zipfile
from datetime import datetime
from pathlib import Path
import importlib.util

def _load_module_from_sibling(py_filename: str, module_name: str):
    """Carga un .py hermano por ruta absoluta (fallback robusto)."""
    here = Path(__file__).resolve().parent
    path = here / py_filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    raise ImportError(f"No se pudo cargar {py_filename} desde {here}")

# ===== export_import =====
try:
    from password_vault.export_import import export_vault_to_blob, import_vault_from_blob  # absoluto
except Exception:
    _mod = _load_module_from_sibling("export_import.py", "pv_export_import")
    export_vault_to_blob = _mod.export_vault_to_blob
    import_vault_from_blob = _mod.import_vault_from_blob

# ===== export_sql =====
try:
    from password_vault.export_sql import build_sql_dump_string  # absoluto
except Exception:
    _mod2 = _load_module_from_sibling("export_sql.py", "pv_export_sql")
    build_sql_dump_string = _mod2.build_sql_dump_string

BUNDLE_META = {"kind": "pmvault-bundle", "version": 1}

def export_unified_pmvault(SessionLocal, key: bytes, outfile_path: str) -> None:
    """
    Crea un solo archivo .pmvault (zip) con:
      - payload.bin (blob cifrado para importación nativa)
      - vault.sql   (dump SQL)
      - meta.json   (metadatos)
    """
    blob = export_vault_to_blob(SessionLocal, key)
    sql_text = build_sql_dump_string(SessionLocal)
    meta = {**BUNDLE_META, "created": datetime.utcnow().isoformat() + "Z"}

    with zipfile.ZipFile(outfile_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
        z.writestr("payload.bin", blob)      # bytes
        z.writestr("vault.sql", sql_text)    # str

def import_unified_pmvault(SessionLocal, key: bytes, infile_path: str, write_sql_alongside: bool = False):
    """
    Importa un .pmvault:
      - Si es bundle (zip): usa payload.bin para restaurar; opcionalmente escribe vault.sql al lado.
      - Si es legacy (blob crudo): lo importa igual.
    Devuelve (inserted_count, sql_path or None).
    """
    if zipfile.is_zipfile(infile_path):
        with zipfile.ZipFile(infile_path, "r") as z:
            if "payload.bin" in z.namelist():
                payload = z.read("payload.bin")
                inserted = import_vault_from_blob(SessionLocal, key, payload)
                sql_out = None
                if write_sql_alongside and "vault.sql" in z.namelist():
                    base, _ = os.path.splitext(infile_path)
                    sql_out = base + ".sql"
                    with open(sql_out, "wb") as fh:
                        fh.write(z.read("vault.sql"))
                return inserted, sql_out

    # Legacy: archivo no-zip o zip sin payload.bin
    with open(infile_path, "rb") as fh:
        blob = fh.read()
    inserted = import_vault_from_blob(SessionLocal, key, blob)
    return inserted, None
