import os

import os
from dotenv import load_dotenv
load_dotenv()  # lee .env
def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///vault.db")


def get_database_url() -> str:
    # Por defecto usa SQLite local 'vault.db' en la raíz del proyecto
    return os.environ.get("DATABASE_URL", "sqlite:///vault.db")
