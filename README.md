# 🔐 PasswordVault
**PasswordVault** es un gestor de contraseñas seguro escrito en **Python**, diseñado para almacenar credenciales de forma cifrada y accesible a través de una interfaz gráfica sencilla.

---

## 🚀 Características
- 🔑 Gestión segura de contraseñas con cifrado.
- 🗄️ Base de datos SQLite almacenada en `%APPDATA%/PasswordVault`.
- 💻 Interfaz gráfica con **Tkinter**.
- 🌗 Soporte de temas (oscuro/claro).
- 📤 Importar / exportar bóvedas.
- 🧩 Código modular y fácil de extender.

---

## 📂 Estructura del proyecto
passwordvault/  
├── password_vault/ → Código fuente principal  
│   ├── app.py → Punto de entrada de la aplicación  
│   ├── config.py → Configuración general  
│   ├── crypto.py → Funciones de cifrado  
│   ├── db.py → Modelos y conexión a la base de datos  
│   ├── events.py → Eventos de la interfaz  
│   ├── export_import.py → Exportación e importación de datos  
│   ├── export_sql.py → Exportación a SQL  
│   ├── pmvault_bundle.py → Empaquetado / utilidades  
│   ├── ui.py → Interfaz gráfica (Tkinter)  
│   └── __init__.py  
├── requirements.txt → Dependencias del proyecto  
├── run.py → Script para ejecutar la aplicación  
├── .gitignore → Archivos ignorados en Git  
└── README.md → Este archivo  

---

## ⚙️ Instalación
1. Clonar el repositorio:  
   `git clone https://github.com/Litdemonick/passwordvault.git`  
   `cd passwordvault`

2. Crear un entorno virtual:  
   `python -m venv .venv`

3. Activar el entorno:  
   - En Windows: `.venv\Scripts\activate`  
   - En Linux/Mac: `source .venv/bin/activate`

4. Instalar dependencias:  
   `pip install -r requirements.txt`

---

## ▶️ Uso
Para ejecutar la aplicación:  
`python run.py`

---

## 📦 Compilar a ejecutable (opcional)
Si quieres generar un `.exe` (Windows) con PyInstaller:  
`pyinstaller --noconsole --onefile run.py`  
El ejecutable aparecerá en la carpeta `dist/`.

---

## 🤝 Contribuir
Actualmente este proyecto es **privado** y no acepta contribuciones externas.  
Si deseas proponer mejoras, por favor contacta al autor.

---

## 📄 Licencia
Copyright (c) 2025 Carlos Miranda.  
Todos los derechos reservados.  

Este software es de **uso privado**:  
- ✔️ Puedes ver el código con fines educativos.  
- ❌ No está permitido copiar, modificar, redistribuir ni usar con fines comerciales sin autorización expresa del autor.
