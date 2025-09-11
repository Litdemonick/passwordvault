import os
import re
import string
import secrets
import configparser
from .login import LoginWindow
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from sqlalchemy import select

from .events import vault_events

from .pmvault_bundle import export_unified_pmvault, import_unified_pmvault
from .db import SessionLocal, Entry, Setting, init_db
from .crypto import (
    derive_key, make_verifier, verify_master,
    encrypt_text, decrypt_text
)





# --- Persistencia del tema en %LOCALAPPDATA%\PasswordVault\vault_ui.ini ---
APP_NAME = "PasswordVault"
APP_VERSION = "1.0.0.0"

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



def _load_saved_theme(default=_DEFAULT_LIGHT) -> str:
    cfg = configparser.ConfigParser()
    try:
        if _UI_INI_PATH.exists():
            cfg.read(_UI_INI_PATH, encoding="utf-8")
            return cfg.get(_UI_INI_SECTION, _UI_INI_KEY, fallback=default)
    except Exception:
        pass
    return default



def _save_theme(theme: str) -> None:
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

# -------- tema y bootstrap --------
USE_BOOTSTRAP = True
try:
    import ttkbootstrap as tb
    from ttkbootstrap.constants import PRIMARY, INFO, SUCCESS, DANGER, SECONDARY
except Exception:
    USE_BOOTSTRAP = False
    tb = None  # safety

# ------------------ utilidades ------------------

def generate_password(n: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{};:,.?"
    return "".join(secrets.choice(alphabet) for _ in range(n))

def extract_email_from_notes(notes: Optional[str]) -> str:
    """Si no hay columna email, intentamos leer 'Email: ...' de las notas."""
    if not notes:
        return ""
    m = re.search(r"(?im)^\s*email\s*:\s*([^\s]+)\s*$", notes)
    return m.group(1) if m else ""

def set_email_on_entry(entry, email: str):
    """Setea email en Entry si existe la columna; si no, lo guarda en notas con prefijo."""
    if hasattr(entry, "email"):
        setattr(entry, "email", email)
    else:
        # evita duplicados de la línea Email:
        lines = (entry.notes or "").splitlines()
        lines = [ln for ln in lines if not re.match(r"(?im)^\s*email\s*:", ln)]
        if email:
            lines.append(f"Email: {email}")
        entry.notes = "\n".join([ln for ln in lines if ln]).strip()

def get_email_from_entry(entry) -> str:
    """Lee el email de Entry ya sea por columna o por notas."""
    if hasattr(entry, "email") and getattr(entry, "email") is not None:
        return getattr(entry, "email") or ""
    return extract_email_from_notes(entry.notes)

# --------- Panel embebido de master password (sin popups) ----------
class MasterGate:
    """
    Panel de acceso embebido:
    - Si es primera vez: pide y confirma la master password.
    - Si ya existe: solo pide la master.
    Cuando valida, llama a self.on_unlock(key) y destruye el panel.
    """
    def __init__(self, root):
        self.root = root
        with SessionLocal() as s:
            self.setting = s.query(Setting).first()
        self.first_run = self.setting is None

        # Widgets según backend
        Frame  = (tb.Frame if USE_BOOTSTRAP else ttk.Frame)
        Label  = (tb.Label if USE_BOOTSTRAP else ttk.Label)
        EntryW = (tb.Entry if USE_BOOTSTRAP else ttk.Entry)
        Button = (tb.Button if USE_BOOTSTRAP else ttk.Button)
        StrVar = (tb.StringVar if USE_BOOTSTRAP else tk.StringVar)

        # contenedor a pantalla completa
        self.wrap = Frame(self.root, padding=24)
        self.wrap.pack(fill="both", expand=True)

        # “card” centrada
        self.card = Frame(self.wrap, padding=24)
        self.card.place(relx=0.5, rely=0.5, anchor="center")
        self.card.grid_columnconfigure(0, weight=1)

        # Título / subtítulo
        (tb.Label if USE_BOOTSTRAP else tk.Label)(
            self.card,
            text=("Crea tu bóveda" if self.first_run else "Desbloquear bóveda"),
            font=("Segoe UI", 18, "bold")
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        (tb.Label if USE_BOOTSTRAP else tk.Label)(
            self.card,
            text=("Configura una contraseña maestra segura."
                  if self.first_run else "Introduce tu contraseña maestra para continuar."),
            **({"padding": (0, 8)} if USE_BOOTSTRAP else {"pady": 6})
        ).grid(row=1, column=0, columnspan=3, sticky="w")

        # Campo master
        Label(self.card, text="Contraseña maestra").grid(row=2, column=0, columnspan=2, sticky="w")
        self.var_pwd = StrVar()
        self.e_pwd = EntryW(self.card, textvariable=self.var_pwd, show="*", width=46)
        self.e_pwd.grid(row=3, column=0, sticky="ew", padx=(0, 8))
        Button(self.card, text="👁", width=3,
               command=lambda: self._toggle(self.e_pwd),
               **({"bootstyle": SECONDARY} if USE_BOOTSTRAP else {})).grid(row=3, column=1, sticky="w")

        # Confirmación si primera vez
        self.var_pwd2 = None
        self.e_pwd2 = None
        if self.first_run:
            Label(self.card, text="Repite la contraseña").grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))
            self.var_pwd2 = StrVar()
            self.e_pwd2 = EntryW(self.card, textvariable=self.var_pwd2, show="*", width=46)
            self.e_pwd2.grid(row=5, column=0, sticky="ew", padx=(0, 8))
            Button(self.card, text="👁", width=3,
                   command=lambda: self._toggle(self.e_pwd2),
                   **({"bootstyle": SECONDARY} if USE_BOOTSTRAP else {})).grid(row=5, column=1, sticky="w")

        # Mensaje inline de error
        self.var_msg = StrVar()
        (tb.Label if USE_BOOTSTRAP else tk.Label)(
            self.card, textvariable=self.var_msg,
            **({"padding": (0, 6), "foreground": "#d33"} if USE_BOOTSTRAP else {"pady": 6, "fg": "#d33"})
        ).grid(row=6, column=0, columnspan=3, sticky="w")

        # Acciones
        Button(self.card,
               text=("Crear bóveda" if self.first_run else "Desbloquear"),
               command=self._accept,
               width=18,
               **({"bootstyle": PRIMARY} if USE_BOOTSTRAP else {})).grid(row=7, column=0, pady=(6, 0), sticky="w")
        Button(self.card, text="Salir", command=self.root.destroy).grid(row=7, column=1, pady=(6, 0), sticky="e")

        self.e_pwd.focus_set()
        self.on_unlock = lambda key: None  # será asignado por main()

    def _toggle(self, entry):
        entry.config(show="" if entry.cget("show") == "*" else "*")
        entry.focus_set()

    def _accept(self):
        p1 = self.var_pwd.get()
        if not p1:
            self.var_msg.set("La contraseña no puede estar vacía.")
            self.e_pwd.focus_set()
            return

        if self.first_run:
            p2 = self.var_pwd2.get() if self.var_pwd2 else ""
            if p1 != p2:
                self.var_msg.set("Las contraseñas no coinciden.")
                (self.e_pwd2 or self.e_pwd).focus_set()
                return
            salt = os.urandom(16)
            key = derive_key(p1, salt)
            verifier = make_verifier(key)
            with SessionLocal() as s:
                s.add(Setting(kdf_salt=salt, verifier=verifier))
                s.commit()
            self.destroy()
            self.on_unlock(key)
        else:
            with SessionLocal() as s:
                st = s.query(Setting).first()
            if not st:
                self.var_msg.set("No hay configuración de bóveda.")
                return
            key = derive_key(p1, st.kdf_salt)
            if not verify_master(key, st.verifier):
                self.var_msg.set("Contraseña incorrecta.")
                self.e_pwd.focus_set()
                self.e_pwd.selection_range(0, 'end')
                return
            self.destroy()
            self.on_unlock(key)

    def set_on_unlock(self, fn):
        self.on_unlock = fn

    def destroy(self):
        self.wrap.destroy()

# ------------------ Diálogo de entrada ------------------

class EntryDialog:
    """Alta/edición de entrada."""
    def __init__(self, master, data=None):
        self.top = (tb.Toplevel(master) if USE_BOOTSTRAP else tk.Toplevel(master))
        self.top.title("Entrada")
        self.top.resizable(False, False)

        Frame = tb.Frame if USE_BOOTSTRAP else ttk.Frame
        Label = tb.Label if USE_BOOTSTRAP else ttk.Label
        EntryW = tb.Entry if USE_BOOTSTRAP else ttk.Entry
        TextW = tb.Text if USE_BOOTSTRAP else tk.Text
        Button = tb.Button if USE_BOOTSTRAP else ttk.Button

        P = 10
        frm = Frame(self.top, padding=P); frm.grid(sticky="nsew")
        frm.columnconfigure(1, weight=1)

        # Título
        Label(frm, text="Título").grid(row=0, column=0, sticky="w")
        self.e_title = EntryW(frm, width=46); self.e_title.grid(row=0, column=1, sticky="ew")

        # Usuario (DB: username)
        Label(frm, text="Usuario").grid(row=1, column=0, sticky="w")
        self.e_user = EntryW(frm, width=46); self.e_user.grid(row=1, column=1, sticky="ew")

        # Correo (DB: email si existe; si no, a notas con prefijo)
        Label(frm, text="Correo").grid(row=2, column=0, sticky="w")
        self.e_email = EntryW(frm, width=46); self.e_email.grid(row=2, column=1, sticky="ew")

        # URL
        Label(frm, text="URL").grid(row=3, column=0, sticky="w")
        self.e_url = EntryW(frm, width=46); self.e_url.grid(row=3, column=1, sticky="ew")

        # Notas
        Label(frm, text="Notas").grid(row=4, column=0, sticky="nw")
        self.t_notes = TextW(frm, width=46, height=6); self.t_notes.grid(row=4, column=1, sticky="ew")

        # Contraseña
        Label(frm, text="Contraseña").grid(row=5, column=0, sticky="w")
        self.e_pwd = EntryW(frm, width=46, show="*"); self.e_pwd.grid(row=5, column=1, sticky="ew")

        # Botones
        btns = Frame(frm); btns.grid(row=6, column=0, columnspan=2, sticky="e", pady=(8, 0))
        Button(btns, text="Generar", command=self.on_gen,
               **({"bootstyle": SECONDARY} if USE_BOOTSTRAP else {})).grid(row=0, column=0, padx=4)
        Button(btns, text="Guardar", command=self.on_ok,
               **({"bootstyle": SUCCESS} if USE_BOOTSTRAP else {})).grid(row=0, column=1, padx=4)
        Button(btns, text="Cancelar", command=self.top.destroy).grid(row=0, column=2, padx=4)

        if data:
            self.e_title.insert(0, data.get("title", ""))
            self.e_user.insert(0, data.get("username", ""))  # username
            # email puede venir directo o extraerse de notas
            email_prefill = data.get("email", "") or extract_email_from_notes(data.get("notes", ""))
            self.e_email.insert(0, email_prefill)
            self.e_url.insert(0, data.get("url", ""))
            self.t_notes.insert("1.0", data.get("notes", ""))

        self.result = None
        self.top.grab_set()
        self.e_title.focus_set()

    def on_gen(self):
        self.e_pwd.delete(0, "end")
        self.e_pwd.insert(0, generate_password(20))

    def on_ok(self):
        title = self.e_title.get().strip()
        user = self.e_user.get().strip()
        email = self.e_email.get().strip()
        url = self.e_url.get().strip()
        notes = self.t_notes.get("1.0", "end").strip()
        pwd = self.e_pwd.get()

        if not title or not pwd:
            messagebox.showerror("Error", "Título y Contraseña son obligatorios.", parent=self.top)
            return   # 🔹 ahora el return SOLO se ejecuta si hay error

        # Guardamos los datos en self.result
        self.result = {
            "title": title,
            "username": user,
            "email": email,
            "url": url,
            "notes": notes,
            "password": pwd,
        }

        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()






# ------------------ App principal ------------------

class PasswordVaultApp:
    def __init__(self, root, derived_key: bytes, start_theme: str = _DEFAULT_LIGHT):
        self.root = root
        self.derived_key = derived_key
        self.key = derived_key          # compat con el resto de métodos
        self.style = (tb.Style() if USE_BOOTSTRAP else ttk.Style())
        self.current_theme = start_theme

        # ====== Construcción de UI (AHORA RESPONSIVA) ======
        Frame = (tb.Frame if USE_BOOTSTRAP else ttk.Frame)

        self.app = Frame(self.root, padding=0)
        self.app.pack(fill="both", expand=True)

        # Layout principal con grid (sidebar + contenido)
        main = Frame(self.app, padding=0)
        main.pack(fill="both", expand=True)

        main.grid_rowconfigure(0, weight=1)     # fila expansible
        main.grid_columnconfigure(0, weight=0)  # sidebar fijo
        main.grid_columnconfigure(1, weight=1)  # contenido expansible

        sidebar = self._build_sidebar(main)
        sidebar.grid(row=0, column=0, sticky="ns")  # ocupa alto completo

        content = self._build_content(main)
        content.grid(row=0, column=1, sticky="nsew")  # se expande

        # Suscripción a eventos (después de construir la UI)
        vault_events.entry_changed.connect(self._on_entry_changed)

        # Carga inicial de la tabla
        self.refresh_table()
        self.set_status("Bienvenido a PasswordVault")
        # =======================================================


    # === Helpers de tema / Treeview (DENTRO de la clase) ===
    def _is_dark(self) -> bool:
        return (self.current_theme or "").lower() in {"darkly"}

    def _tv_bg(self):      # fondo normal de la tabla
        return "#1f1f1f" if self._is_dark() else "#ffffff"

    def _tv_fg(self):      # texto normal
        return "#e9e9e9" if self._is_dark() else "#0f0f0f"

    def _sel_bg(self):     # fondo cuando está seleccionado
        return "#0d6efd"

    def _sel_fg(self):     # texto cuando está seleccionado
        return "#ffffff"

    def _alt_row_bg(self): # color de filas alternas
        return "#2b2b2b" if self._is_dark() else "#fafafa"

    def _apply_treeview_style(self):
        """
        Estilo visual del Treeview tipo tabla de DB:
        - Bordes visibles
        - Encabezados centrados con fondo oscuro
        - Filas alternas
        - Selección destacada
        """
        style = self.style

        # Estilo para las filas
        style.configure(
            "Treeview",
            background=self._tv_bg(),
            fieldbackground=self._tv_bg(),
            foreground=self._tv_fg(),
            rowheight=28,  # más alto que antes
            font=("Segoe UI", 10),
            bordercolor="#444444",
            borderwidth=1,
            relief="solid"
        )

        # Estilo para los encabezados
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 11, "bold"),
            background="#2d2d2d",
            foreground="#ffffff",
            bordercolor="#444444",
            borderwidth=1,
            relief="solid",
            anchor="center"  # títulos centrados
        )

        # Estilo dinámico (selección)
        style.map("Treeview",
                background=[("selected", self._sel_bg())],
                foreground=[("selected", self._sel_fg())])

        # Estilos para filas alternas
        try:
            self.tree.tag_configure("row", borderwidth=1, relief="solid")
            self.tree.tag_configure("evenrow", background=self._tv_bg())
            self.tree.tag_configure("oddrow", background=self._alt_row_bg())
        except Exception:
            pass


    # Texto del botón acorde al tema
    def _update_theme_button_text(self):
        if self.current_theme == _DEFAULT_DARK:
            self.btn_theme.config(text="☀️ Modo claro")
        else:
            self.btn_theme.config(text="🌙 Modo oscuro")

    # Fade no bloqueante
    def _fade(self, start: float, end: float, steps: int = 12, delay_ms: int = 18, then=None):
        start = max(0.0, min(1.0, start))
        end   = max(0.0, min(1.0, end))
        delta = (end - start) / max(1, steps)
        state = {"i": 0, "alpha": start}

        def step():
            self.root.attributes("-alpha", state["alpha"])
            state["i"] += 1
            state["alpha"] += delta
            if state["i"] <= steps:
                self.root.after(delay_ms, step)
            else:
                self.root.attributes("-alpha", end)
                if callable(then):
                    then()
        step()

    # Aplicar tema con transición
    def _apply_theme_with_fade(self, new_theme: str):
        """
        Cambia entre modo claro y oscuro con transición suave.
        Sin usar transparencia (-alpha), para evitar que la ventana
        se cierre o desaparezca en otros PCs.
        """
        old_bg = self._tv_bg()  # color actual antes del cambio
        self.current_theme = new_theme
        _save_theme(new_theme)

        if USE_BOOTSTRAP:
            self.style.theme_use(new_theme)

        self._update_theme_button_text()

        steps = 15
        delay = 25  # ms entre pasos
        state = {"i": 0}

        def step():
            t = state["i"] / steps
            blended_bg = self._hex_blend(old_bg, self._tv_bg(), t)
            self.style.configure("Treeview", background=blended_bg, fieldbackground=blended_bg)
            self.refresh_table()
            state["i"] += 1
            if state["i"] <= steps:
                self.root.after(delay, step)
            else:
                self._apply_treeview_style()
                self.refresh_table()

        step()


    
    def _hex_blend(self, c1: str, c2: str, t: float) -> str:
        """
        Mezcla dos colores hex (#rrggbb) con un factor t (0.0 → c1, 1.0 → c2).
        """
        c1 = c1.lstrip("#")
        c2 = c2.lstrip("#")
        r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
        r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"




    # Toggle del botón
    def toggle_theme(self):
        new_theme = _DEFAULT_DARK if self.current_theme != _DEFAULT_DARK else _DEFAULT_LIGHT
        self._apply_theme_with_fade(new_theme)


    # sidebar
    def _build_sidebar(self, parent):
        Frame = (tb.Frame if USE_BOOTSTRAP else ttk.Frame)
        Button = (tb.Button if USE_BOOTSTRAP else ttk.Button)
        Label = (tb.Label if USE_BOOTSTRAP else ttk.Label)

        side = Frame(parent, padding=0)
        side.configure(width=260)

        brand = Frame(side, padding=16); brand.pack(fill="x")
        (tb.Label if USE_BOOTSTRAP else tk.Label)(
            brand, text=f"🔐 {APP_NAME} v{APP_VERSION}", font=("Segoe UI", 14, "bold")
        ).pack(anchor="w")


        box = Frame(side, padding=(12, 8)); box.pack(fill="both", expand=True)

        sections = [
            ("Vault", "Todos"),
            ("Favorites", "Favoritos"),
            ("Trash", "Papelera"),
            ]
        for name, tag in sections:
            btn = Button(box, text=f"• {name}", width=18,
                         **({"bootstyle": SECONDARY} if USE_BOOTSTRAP else {}),
                         command=lambda t=tag: self._quick_filter(t))
            btn.pack(anchor="w", pady=3)

        return side

    def _quick_filter(self, text: str):
        self.search_var.set(text)
        self.refresh_table()

        # contenido
    def _build_content(self, parent):
        Frame  = (tb.Frame if USE_BOOTSTRAP else ttk.Frame)
        Button = (tb.Button if USE_BOOTSTRAP else ttk.Button)
        Label  = (tb.Label if USE_BOOTSTRAP else ttk.Label)
        EntryW = (tb.Entry if USE_BOOTSTRAP else ttk.Entry)
        TextW  = (tb.Text if USE_BOOTSTRAP else tk.Text)
        Tree   = (tb.Treeview if USE_BOOTSTRAP else ttk.Treeview)

        cont = Frame(parent, padding=0)
        cont.grid_rowconfigure(2, weight=1)     # la tabla se expande
        cont.grid_columnconfigure(0, weight=1)

        # --- Header ---
        header = Frame(cont, padding=(12, 12))
        header.grid(row=0, column=0, sticky="ew")
        self.header = header

        (tb.Label if USE_BOOTSTRAP else tk.Label)(
            header, text="Vault", font=("Segoe UI", 18, "bold")
        ).pack(side="left")

        right = Frame(header)
        right.pack(side="right")

        self.search_var = (tb.StringVar() if USE_BOOTSTRAP else tk.StringVar())
        self.e_search = EntryW(right, textvariable=self.search_var, width=40)
        self.e_search.pack(side="left", padx=(0, 8))
        self.e_search.bind("<KeyRelease>", lambda e: self.refresh_table())

        Button(
            right, text="+ New",
            **({"bootstyle": PRIMARY} if USE_BOOTSTRAP else {}),
            command=self.add_entry
        ).pack(side="left")

        if USE_BOOTSTRAP:
            self.btn_theme = tb.Button(
                right,
                text="🌙 Modo oscuro",
                bootstyle="secondary-outline",
                command=self.toggle_theme
            )
            self.btn_theme.pack(side="left", padx=(8, 0))
            self._update_theme_button_text()

        # --- Toolbar ---
        toolbar = Frame(cont, padding=(12, 0))
        toolbar.grid(row=1, column=0, sticky="ew")

        Button(toolbar, text="Editar",
            **({"bootstyle": INFO} if USE_BOOTSTRAP else {}),
            command=self.edit_entry).pack(side="left", padx=4, pady=6)
        Button(toolbar, text="Eliminar",
            **({"bootstyle": DANGER} if USE_BOOTSTRAP else {}),
            command=self.delete_entry).pack(side="left", padx=4, pady=6)
        Button(toolbar, text="Copiar",
            **({"bootstyle": SECONDARY} if USE_BOOTSTRAP else {}),
            command=self.copy_password).pack(side="left", padx=4, pady=6)
        Button(toolbar, text="Export",
            **({"bootstyle": SUCCESS} if USE_BOOTSTRAP else {}),
            command=self.export_vault).pack(side="left", padx=4, pady=6)
        Button(toolbar, text="Import",
            **({"bootstyle": SECONDARY} if USE_BOOTSTRAP else {}),
            command=self.import_vault).pack(side="left", padx=4, pady=6)

        # --- Tabla + scrollbars ---
        table_wrap = Frame(cont, padding=(12, 8))
        table_wrap.grid(row=2, column=0, sticky="nsew")
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        self.tree = Tree(
            table_wrap,
            columns=("id", "Name", "Usuario", "Correo", "URL", "Updated"),
            show="headings"
        )
        self.tree.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=y_scroll.set)

        x_scroll = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.tree.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.tree.configure(xscrollcommand=x_scroll.set)

        # 🔒 Evita que se puedan mover las columnas con el ratón
        def _block_column_drag(event):
            return "break"
        self.tree.bind("<B1-Motion>", _block_column_drag, add="+")

        # Click derecho en la tabla (context menu)
        self.tree.bind("<Button-3>", self._show_context_menu)

        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="⭐ Añadir a favoritos", command=self._toggle_favorite)
        self.context_menu.add_command(label="🗑️ Mover a papelera", command=self.delete_entry)
        self.context_menu.add_command(label="♻️ Restaurar", command=self.restore_entry)

        # Configuración de columnas
        columns_cfg = [
            ("id", 50, "center"),
            ("Name", 260, "w"),
            ("Usuario", 200, "w"),
            ("Correo", 220, "w"),
            ("URL", 360, "w"),
            ("Updated", 160, "center"),
        ]

        for col, w, align in columns_cfg:
            self.tree.heading(col, text=col, anchor="center")
            self.tree.column(col, width=w, anchor=align, stretch=False)

            # Panel oculto de edición
            self.edit_panel = Frame(cont, padding=(12, 12))
            self.edit_panel.grid(row=3, column=0, sticky="ew")
            self.edit_panel.grid_remove()

            Label(self.edit_panel, text="Título").grid(row=0, column=0, sticky="w")
            self.e_title = EntryW(self.edit_panel, width=46)
            self.e_title.grid(row=0, column=1, sticky="ew", padx=6)

            Label(self.edit_panel, text="Usuario").grid(row=1, column=0, sticky="w")
            self.e_user = EntryW(self.edit_panel, width=46)
            self.e_user.grid(row=1, column=1, sticky="ew", padx=6)

            Label(self.edit_panel, text="Correo").grid(row=2, column=0, sticky="w")
            self.e_email = EntryW(self.edit_panel, width=46)
            self.e_email.grid(row=2, column=1, sticky="ew", padx=6)

            Label(self.edit_panel, text="URL").grid(row=3, column=0, sticky="w")
            self.e_url = EntryW(self.edit_panel, width=46)
            self.e_url.grid(row=3, column=1, sticky="ew", padx=6)

            Label(self.edit_panel, text="Contraseña").grid(row=4, column=0, sticky="w")
            self.e_pwd = EntryW(self.edit_panel, width=46, show="*")
            self.e_pwd.grid(row=4, column=1, sticky="ew", padx=6)

            Label(self.edit_panel, text="Notas").grid(row=5, column=0, sticky="nw")
            self.t_notes = TextW(self.edit_panel, width=46, height=6)
            self.t_notes.grid(row=5, column=1, sticky="ew", padx=6)

            btns = Frame(self.edit_panel)
            btns.grid(row=6, column=0, columnspan=2, pady=(8, 0))

            Button(btns, text="Guardar", command=self._save_entry,
                **({"bootstyle": SUCCESS} if USE_BOOTSTRAP else {})).pack(side="left", padx=4)
            Button(btns, text="Cancelar", command=self._hide_edit_panel).pack(side="left", padx=4)

        # 🔹 Fijar columnas visibles
        self.tree["displaycolumns"] = ("id", "Name", "Usuario", "Correo", "URL", "Updated")

        # --- Status bar ---
        status = Frame(cont, padding=(12, 8))
        status.grid(row=4, column=0, sticky="ew")
        self.status_label = (tb.Label if USE_BOOTSTRAP else ttk.Label)(
            status, text="Listo", anchor="w"
        )
        self.status_label.pack(fill="x")

        self._apply_treeview_style()
        return cont



    


    

    # --- Eventos de dominio ---
    def _on_entry_changed(self, action: str,
                          entry_id: Optional[int] = None,
                          message: Optional[str] = None):
        """
        Refresca la tabla de forma segura desde el hilo de Tk.
        - action: 'add' | 'edit' | 'delete' | 'import'
        - entry_id: opcional
        - message: opcional para status bar
        """
        def _do():
            # Si hay filtro activo y fue 'add', limpiar para que se vea la nueva fila
            if action == "add" and (self.search_var.get() or "").strip():
                self.search_var.set("")
            self.refresh_table()
            if message:
                self.set_status(message)
            else:
                self.set_status({
                    "add": "Añadido",
                    "edit": "Actualizado",
                    "delete": "Eliminado",
                    "import": "Importado"
                }.get(action, "Listo"))
        self.root.after(0, _do)   # asegura ejecución en el loop de Tk

    # helpers
    def set_status(self, msg: str):
        self.status_label.config(text=msg)

    def selected_id(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        return int(vals[0]) if vals else None
    
    def _show_context_menu(self, event):
        try:
            rowid = self.tree.identify_row(event.y)
            if not rowid:
                return
            self.tree.selection_set(rowid)

            # Borrar menú anterior
            self.context_menu = tk.Menu(self.root, tearoff=0)

            # Saber en qué sección estamos
            current_view = (self.search_var.get() or "").strip().lower()

            if current_view == "papelera":
                self.context_menu.add_command(label="♻️ Restaurar", command=self.restore_entry)
                self.context_menu.add_command(label="❌ Eliminar permanentemente", command=self.delete_forever_entry)


            elif current_view == "favoritos":
                # Quitar de favoritos y mover a papelera
                self.context_menu.add_command(label="⭐ Quitar de favoritos", command=self._toggle_favorite)
                self.context_menu.add_command(label="🗑️ Mover a papelera", command=self.delete_entry)

            else:  # Vault / Todos
                self.context_menu.add_command(label="⭐ Añadir a favoritos", command=self._toggle_favorite)
                self.context_menu.add_command(label="🗑️ Mover a papelera", command=self.delete_entry)

            self.context_menu.post(event.x_root, event.y_root)

        finally:
            try:
                self.context_menu.grab_release()
            except Exception:
                pass


    def _show_edit_panel(self, data=None):
        """Muestra el panel con datos prellenados (o vacío para nuevo)."""
        self.e_title.delete(0, "end")
        self.e_user.delete(0, "end")
        self.e_email.delete(0, "end")
        self.e_url.delete(0, "end")
        self.e_pwd.delete(0, "end")
        self.t_notes.delete("1.0", "end")

        if data:
            self.e_title.insert(0, data.get("title", ""))
            self.e_user.insert(0, data.get("username", ""))
            self.e_email.insert(0, data.get("email", ""))
            self.e_url.insert(0, data.get("url", ""))
            self.t_notes.insert("1.0", data.get("notes", ""))

        self.edit_panel.pack(fill="x")  # mostrar panel

    def _hide_edit_panel(self):
        """Oculta el panel."""
        self.edit_panel.pack_forget()



    def delete_forever_entry(self):
        eid = self.selected_id()
        if not eid:
            messagebox.showerror("Error", "Selecciona una fila.", parent=self.root)
            return
        if not messagebox.askyesno("Confirmar", "¿Eliminar esta entrada para siempre?", parent=self.root):
            return
        with SessionLocal() as s:
            e = s.get(Entry, eid)
            if e:
                s.delete(e)
                s.commit()
        self.refresh_table()
        vault_events.entry_changed.emit(
            action="delete", entry_id=eid, message="Eliminado permanentemente"
        )

    
    def _toggle_favorite(self):
        eid = self.selected_id()
        if not eid:
            return
        with SessionLocal() as s:
            e = s.get(Entry, eid)
            if not e:
                return
            e.is_favorite = not e.is_favorite
            s.commit()
        self.refresh_table()
        vault_events.entry_changed.emit(
            action="edit", entry_id=eid,
            message="Marcado como favorito" if e.is_favorite else "Favorito quitado"
        )

    def _load_entries(self):
        q = (self.search_var.get() or "").lower()
        with SessionLocal() as s:
            entries = s.execute(select(Entry).order_by(Entry.updated_at.desc())).scalars().all()

        # Filtrar por papelera/favoritos
        tag = q.strip().lower()
        if tag == "favoritos":
            entries = [e for e in entries if e.is_favorite and not e.deleted_at]
        elif tag == "papelera":
            entries = [e for e in entries if e.deleted_at]
        else:
            # Vault = todos menos los borrados
            entries = [e for e in entries if not e.deleted_at]

        # Si además hay búsqueda por texto
        if q and tag not in ("favoritos", "papelera", "todos"):
            def matches(e: Entry) -> bool:
                email = get_email_from_entry(e).lower()
                hay = [
                    (e.title or "").lower(),
                    (e.username or "").lower(),
                    email,
                    (e.url or "").lower(),
                    (e.notes or "").lower(),
                ]
                return any(q in x for x in hay)
            entries = [e for e in entries if matches(e)]

        return entries


    def refresh_table(self):
        # Limpiar la tabla antes de volver a llenar
        for i in self.tree.get_children():
            self.tree.delete(i)

        # Re-aplica tags de estilo por si cambió el tema
        try:
            self.tree.tag_configure("row", borderwidth=1, relief="solid")
            self.tree.tag_configure("evenrow", background=self._tv_bg())
            self.tree.tag_configure("oddrow", background=self._alt_row_bg())
        except Exception:
            pass

        # Cargar entradas desde la base de datos
        entries = self._load_entries()

        # Insertar filas alternando estilos
        for idx, e in enumerate(entries):
            row_tag = "evenrow" if idx % 2 == 0 else "oddrow"
            email = get_email_from_entry(e)

            self.tree.insert(
                "",
                "end",
                values=(
                    e.id,
                    e.title,
                    e.username or "",
                    email,
                    e.url or "",
                    e.updated_at.strftime("%Y-%m-%d %H:%M")
                ),
                tags=("row", row_tag)
            )

        # Si no hay entradas, insertar una fila vacía para que se vean las líneas completas
        if not entries:
            self.tree.insert(
                "",
                "end",
                values=("", "", "", "", "", ""),
                tags=("row", "evenrow")
            )

        # Actualizar la barra de estado
        self.set_status(f"{len(entries)} items")



    # acciones
    def add_entry(self):
        dlg = EntryDialog(self.root)
        self.root.wait_window(dlg.top)
        if not getattr(dlg, "result", None):
            return
        d = dlg.result
        try:
            ct = encrypt_text(self.key, d["password"] or generate_password(16))
            with SessionLocal() as s:
                entry = Entry(
                    title=d["title"],
                    username=d["username"],  # Usuario
                    url=d["url"],
                    notes=d["notes"],
                    password_encrypted=ct
                )
                set_email_on_entry(entry, d["email"])
                s.add(entry)
                s.commit()
                new_id = entry.id
            # Refresco local + señal
            self.refresh_table()
            vault_events.entry_changed.emit(action="add", entry_id=new_id, message="Añadido")
        except Exception as ex:
            messagebox.showerror("Error", f"No se pudo guardar: {ex}", parent=self.root)






    def edit_entry(self):
        eid = self.selected_id()
        if not eid:
            messagebox.showerror("Error", "Selecciona una fila.", parent=self.root)
            return
        with SessionLocal() as s:
            e = s.get(Entry, eid)
            if not e:
                messagebox.showerror("Error", "Entrada no encontrada.", parent=self.root)
                return
            dlg = EntryDialog(self.root, data={
                "title": e.title,
                "username": e.username,
                "email": get_email_from_entry(e),
                "url": e.url,
                "notes": e.notes
            })
            self.root.wait_window(dlg.top)
            if not getattr(dlg, "result", None):
                return
            d = dlg.result
            try:
                e.title = d["title"]
                e.username = d["username"]
                e.url = d["url"]
                e.notes = d["notes"]
                set_email_on_entry(e, d["email"])
                if d["password"]:
                    e.password_encrypted = encrypt_text(self.key, d["password"])
                s.commit()
            except Exception as ex:
                messagebox.showerror("Error", f"No se pudo actualizar: {ex}", parent=self.root)
                return
        self.refresh_table()
        vault_events.entry_changed.emit(action="edit", entry_id=eid, message="Actualizado")

        
    def _save_entry(self):
        title = self.e_title.get().strip()
        user = self.e_user.get().strip()
        email = self.e_email.get().strip()
        url = self.e_url.get().strip()
        notes = self.t_notes.get("1.0", "end").strip()
        pwd = self.e_pwd.get()

        if not title or not pwd:  # 🔹 Solo título y contraseña obligatorios
            messagebox.showerror("Error", "Título y contraseña son obligatorios.", parent=self.root)
            return

        try:
            ct = encrypt_text(self.key, pwd or generate_password(16))
            with SessionLocal() as s:
                entry = Entry(
                    title=title,
                    username=user,
                    url=url,
                    notes=notes,
                    password_encrypted=ct
                )
                set_email_on_entry(entry, email)
                s.add(entry)
                s.commit()
                new_id = entry.id
            self.refresh_table()
            vault_events.entry_changed.emit(action="add", entry_id=new_id, message="Añadido")
            self._hide_edit_panel()
        except Exception as ex:
            messagebox.showerror("Error", f"No se pudo guardar: {ex}", parent=self.root)


    def delete_entry(self):
        current_view = (self.search_var.get() or "").strip().lower()
        eid = self.selected_id()
        if not eid:
            messagebox.showerror("Error", "Selecciona una fila.", parent=self.root)
            return

        with SessionLocal() as s:
            e = s.get(Entry, eid)
            if not e:
                return

            if current_view == "papelera":
                # Aquí se hace eliminación permanente
                if messagebox.askyesno("Confirmar", "¿Eliminar esta entrada para siempre?", parent=self.root):
                    s.delete(e)
                    s.commit()
                    self.refresh_table()
                    vault_events.entry_changed.emit(action="delete", entry_id=eid, message="Eliminado permanentemente")
            else:
                # Mover a papelera
                if messagebox.askyesno("Confirmar", "¿Mover esta entrada a la papelera?", parent=self.root):
                    from datetime import datetime
                    e.deleted_at = datetime.utcnow()
                    s.commit()
                    self.refresh_table()
                    vault_events.entry_changed.emit(action="delete", entry_id=eid, message="Movido a papelera")


    def restore_entry(self):
        eid = self.selected_id()
        if not eid:
            return
        with SessionLocal() as s:
            e = s.get(Entry, eid)
            if e:
                e.deleted_at = None
                s.commit()
        self.refresh_table()
        vault_events.entry_changed.emit(
            action="edit",
            entry_id=eid,
            message="Restaurado desde papelera"
        )



    def copy_password(self):
        eid = self.selected_id()
        if not eid:
            messagebox.showerror("Error", "Selecciona una fila.", parent=self.root)
            return
        with SessionLocal() as s:
            e = s.get(Entry, eid)
            if not e:
                messagebox.showerror("Error", "Entrada no encontrada.", parent=self.root)
                return
        try:
            pwd = decrypt_text(self.key, e.password_encrypted)
        except Exception as ex:
            messagebox.showerror("Error", f"No se pudo descifrar: {ex}", parent=self.root)
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(pwd)
        self.set_status("Copiado (se limpia en 20s)")
        self.root.after(20_000, lambda: (self.root.clipboard_clear(), self.set_status("Portapapeles limpiado")))

    def export_vault(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".pmvault",
            filetypes=[("Cofre PasswordVault", ".pmvault")],
            initialfile="vault.pmvault",
            parent=self.root,
        )
        if not path:
            return
        try:
            export_unified_pmvault(SessionLocal, self.key, path)
            messagebox.showinfo(
                "Exportar",
                "Exportación completada.\nSe generó un único archivo .pmvault con el dump SQL embebido.",
                parent=self.root
            )
            self.set_status(f"Exportado a {os.path.basename(path)}")
        except Exception as ex:
            messagebox.showerror("Error", f"No se pudo exportar: {ex}", parent=self.root)

    def import_vault(self):
        path = filedialog.askopenfilename(
            filetypes=[("Cofre PasswordVault", ".pmvault")], parent=self.root
        )
        if not path:
            return
        try:
            # Si quieres dejar un vault.sql junto al archivo al importar, pon True.
            inserted, _ = import_unified_pmvault(
                SessionLocal, self.key, path, write_sql_alongside=False
            )
            messagebox.showinfo("Importar", f"Entradas añadidas: {inserted}", parent=self.root)
            self.refresh_table()
            vault_events.entry_changed.emit(action="import", entry_id=None, message=f"Importadas {inserted}")
        except Exception as ex:
            messagebox.showerror("Error", f"No se pudo importar: {ex}", parent=self.root)
    

def main():
    # DB
    init_db()

    # --- Cargar el tema guardado (o claro por defecto) ---
    start_theme = _load_saved_theme(_DEFAULT_LIGHT)

    # Ventana principal
    if USE_BOOTSTRAP:
        root = tb.Window(themename=start_theme)
    else:
        root = tk.Tk()

    root.title(f"{APP_NAME} v{APP_VERSION}")
    root.geometry("1200x720")

    # ✅ Límites de tamaño
    root.minsize(1000, 600)   # No se puede hacer más pequeña que esto
    # root.maxsize(1920, 1080)  # (Opcional) Si quieres un límite máximo

    # 👇 Ahora usamos LoginWindow en vez de MasterGate
    from .login import LoginWindow

    def _continue_app(derived_key: bytes):
        # Cuando login es correcto → lanzar la app principal
        PasswordVaultApp(root, derived_key, start_theme=start_theme)

    # Se inicializa el login (si es la primera vez pedirá crear master password)
    LoginWindow(root, on_login=_continue_app)


    root.mainloop()
