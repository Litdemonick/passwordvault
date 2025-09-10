```md
# PasswordVault 🔐 (Tkinter + SQLAlchemy)


Gestor de contraseñas con:
- GUI Tkinter
- Cifrado Scrypt + Fernet (AES + HMAC)
- Master password (no se guarda en claro)
- SQLite por defecto / MySQL opcional
- Exportar/Importar `.pmvault` **cifrado**


## Requisitos
- Python 3.10+


```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
```


## Base de Datos (opciones)
- **SQLite (por defecto)**: sin configuración (archivo `vault.db`).
- **MySQL**: crea la BD/usuario y exporta `DATABASE_URL`.


### Crear BD MySQL (Workbench o consola)
```sql
CREATE DATABASE password_vault CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'vaultuser'@'localhost' IDENTIFIED BY 'TuClaveFuerte123!';
GRANT ALL PRIVILEGES ON password_vault.* TO 'vaultuser'@'localhost';
FLUSH PRIVILEGES;
```


### Variables de entorno
Copia `.env.example` a `.env` y ajusta.


## Ejecutar
```bash
python run.py
```


## Tests
```bash
pytest -q
```
```


---