# password_vault/login.py
from PIL import Image, ImageTk
import ttkbootstrap as tb
import tkinter as tk
from pathlib import Path
from .constants import APP_NAME, APP_VERSION


# --- al inicio del archivo login.py ---
import ctypes
from sys import platform

def set_dark_titlebar(window):
    if platform == "win32":
        try:
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(ctypes.c_int(1)),
                ctypes.sizeof(ctypes.c_int(1))
            )
        except Exception as e:
            print("⚠️ No se pudo aplicar dark titlebar:", e)



class LoginWindow(tb.Frame):
    def __init__(self, master, on_login=None):
        super().__init__(master)
        self.pack(fill="both", expand=True)

        self.on_login = on_login or (lambda u, p: None)

        # --- Configuración de la ventana ---
        master.geometry("1200x720")
        master.minsize(1000, 600)
        master.title(f"{APP_NAME} {APP_VERSION}")

        # 🔥 Aplica dark titlebar justo aquí
        set_dark_titlebar(master)

        # === Fondo ===
        bg_path = Path(__file__).parent / "assets" / "fondo.png"
        if bg_path.exists():
            self.bg_img_orig = Image.open(bg_path)
            self.bg_img = ImageTk.PhotoImage(self.bg_img_orig)

            self.bg_label = tk.Label(
                self, image=self.bg_img,
                borderwidth=0, highlightthickness=0
            )
            # ⬇️ Aquí dejamos márgenes de 2% en cada lado
            self.bg_label.place(relx=0.02, rely=0.02,
                                relwidth=0.96, relheight=0.96)

            # Escalar fondo cuando se cambia el tamaño
            self.bind("<Configure>", self._resize_bg)
        else:
            self.config(style="primary.TFrame")

        # === Card centrado (formulario de login) ===
        card = tb.Frame(self, padding=30, bootstyle="secondary")
        card.place(relx=0.5, rely=0.5, anchor="center")

        tb.Label(
            card,
            text="Iniciar sesión",
            font=("Segoe UI", 16, "bold")
        ).pack(pady=10)

        self.var_user = tb.StringVar()
        self.var_pwd = tb.StringVar()

        tb.Entry(card, textvariable=self.var_user,
                 width=30).pack(pady=6)
        tb.Entry(card, textvariable=self.var_pwd,
                 show="*", width=30).pack(pady=6)

        tb.Button(
            card,
            text="Entrar",
            bootstyle="success",
            command=self._do_login
        ).pack(pady=10)

    # --- Escalar el fondo ---
    def _resize_bg(self, event):
        if hasattr(self, "bg_img_orig") and event.width > 0 and event.height > 0:
            # ajustamos al 96% del tamaño actual
            w = int(event.width * 0.96)
            h = int(event.height * 0.96)
            resized = self.bg_img_orig.resize((w, h), Image.LANCZOS)
            self.bg_img = ImageTk.PhotoImage(resized)
            self.bg_label.config(image=self.bg_img)
            self.bg_label.image = self.bg_img

    # --- Acción de login ---
    def _do_login(self):
        user = self.var_user.get().strip()
        pwd = self.var_pwd.get().strip()
        if not user or not pwd:
            tb.dialogs.Messagebox.show_error(
                "Usuario y contraseña requeridos", "Error"
            )
            return
        self.on_login(user, pwd)
