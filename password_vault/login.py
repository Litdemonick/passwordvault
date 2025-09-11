# password_vault/login.py
import os
import tkinter as tk
import ttkbootstrap as tb
from sqlalchemy.orm import Session

from .db import SessionLocal, Setting
from .crypto import derive_key, verify_master, make_verifier


class LoginWindow:
    def __init__(self, master, on_success):
        """
        Ventana de login.
        - master: root window (Tk o tb.Window)
        - on_success: callback que recibe la derived_key cuando se valida
        """
        self.master = master
        self.on_success = on_success

        self.setting = None
        with SessionLocal() as s:
            self.setting = s.query(Setting).first()
        self.first_run = self.setting is None

        # Widgets
        Frame = tb.Frame
        Label = tb.Label
        EntryW = tb.Entry
        Button = tb.Button
        StrVar = tb.StringVar

        self.wrap = Frame(master, padding=30)
        self.wrap.pack(fill="both", expand=True)

        Label(self.wrap, text="🔐 PasswordVault", font=("Segoe UI", 18, "bold")).pack(pady=(0, 12))

        self.var_pwd = StrVar()
        self.e_pwd = EntryW(self.wrap, textvariable=self.var_pwd, show="*", width=40)
        self.e_pwd.pack(pady=6)

        if self.first_run:
            Label(self.wrap, text="Confirmar contraseña:").pack()
            self.var_pwd2 = StrVar()
            self.e_pwd2 = EntryW(self.wrap, textvariable=self.var_pwd2, show="*", width=40)
            self.e_pwd2.pack(pady=6)
        else:
            self.var_pwd2 = None

        self.var_msg = StrVar()
        Label(self.wrap, textvariable=self.var_msg, foreground="#d33").pack()

        Button(self.wrap, text="Aceptar", bootstyle="primary", command=self._accept).pack(pady=8)
        Button(self.wrap, text="Salir", command=self.master.destroy).pack()

        self.e_pwd.focus_set()

    def _accept(self):
        p1 = self.var_pwd.get().strip()
        if not p1:
            self.var_msg.set("La contraseña no puede estar vacía.")
            return

        if self.first_run:
            p2 = self.var_pwd2.get().strip()
            if p1 != p2:
                self.var_msg.set("Las contraseñas no coinciden.")
                return
            # Guardamos master
            salt = os.urandom(16)
            key = derive_key(p1, salt)
            verifier = make_verifier(key)
            with SessionLocal() as s:
                s.add(Setting(kdf_salt=salt, verifier=verifier))
                s.commit()
            self.on_success(key)
            self.wrap.destroy()
        else:
            st = self.setting
            key = derive_key(p1, st.kdf_salt)
            if not verify_master(key, st.verifier):
                self.var_msg.set("Contraseña incorrecta.")
                return
            self.on_success(key)
            self.wrap.destroy()
