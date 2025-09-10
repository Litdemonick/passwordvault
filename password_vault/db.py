import os
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, String, LargeBinary, DateTime, Integer, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

# ===== Ruta segura para la BD =====
APPDATA_DIR = os.path.join(os.getenv("APPDATA"), "PasswordVault")
os.makedirs(APPDATA_DIR, exist_ok=True)  # crea la carpeta si no existe
DB_PATH = os.path.join(APPDATA_DIR, "vault.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# ===== Engine/Session =====
def build_engine(url: Optional[str] = None):
    return create_engine(url or DATABASE_URL, future=True)

engine = build_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

# ===== Modelos =====
class Base(DeclarativeBase):
    pass

class Setting(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kdf_salt: Mapped[bytes] = mapped_column(LargeBinary)
    verifier: Mapped[bytes] = mapped_column(LargeBinary)

class Entry(Base):
    __tablename__ = "entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Campos principales
    title: Mapped[str] = mapped_column(String(255))
    username: Mapped[str] = mapped_column(String(255))

    # 🔹 Email real en la BD (nullable para no romper datos antiguos)
    email: Mapped[Optional[str]] = mapped_column(String(255), default=None)

    url: Mapped[str] = mapped_column(String(512), default="")
    notes: Mapped[str] = mapped_column(String(4096), default="")
    password_encrypted: Mapped[bytes] = mapped_column(LargeBinary)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Nuevas columnas
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

def init_db(_engine=None):
    (Base.metadata.create_all)(_engine or engine)
