#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: verifica_openrouter.py
Descripción: Verifica si la API Key de OpenRouter está configurada y activa.
Si no lo está, muestra una interfaz para actualizarla y notifica por Telegram.
"""

import os
import sys
import requests
import tkinter as tk
from tkinter import messagebox, font as tkfont
from pathlib import Path
from dotenv import load_dotenv, set_key

# Agregar raíz del proyecto al path para importar utils
# Estamos en rpa_framework/recordings/sistema/
ROOT_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from rpa_framework.utils.telegram_manager import enviar_alerta_todos
except ImportError:
    try:
        from utils.telegram_manager import enviar_alerta_todos
    except ImportError:
        def enviar_alerta_todos(msg): print(f"Telegram (Simulado): {msg}")

# Ruta al archivo .env
ENV_PATH = ROOT_DIR / ".env"

def test_api_key(api_key):
    """Verifica si la API Key es válida haciendo una consulta a OpenRouter."""
    if not api_key or api_key == "tu_api_key_aqui":
        return False, "La clave no está configurada o usa el valor por defecto."
    
    url = "https://openrouter.ai/api/v1/auth/key"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://rpa-framework.local"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            # Si el código es 200, la API Key es reconocida por OpenRouter
            return True, "API Key válida y reconocida por OpenRouter."
        elif response.status_code == 401:
            return False, "La API Key es inválida o no tiene permisos."
        elif response.status_code == 429:
            return False, "Has alcanzado el límite de cuota."
        else:
            return False, f"Error de validación (Status: {response.status_code})"
    except Exception as e:
        return False, f"Error de conexión: {str(e)}"

def update_env_key(new_key):
    """Actualiza la clave en el archivo .env."""
    try:
        if not ENV_PATH.exists():
            with open(ENV_PATH, 'w') as f:
                f.write(f"OPENROUTER_API_KEY={new_key}\n")
        else:
            set_key(str(ENV_PATH), "OPENROUTER_API_KEY", new_key)
        return True
    except Exception as e:
        print(f"Error actualizando .env: {e}")
        return False

class KeyUpdateWindow:
    def __init__(self, current_key="", error_msg=""):
        self.root = tk.Tk()
        self.root.title("Configuración OpenRouter API Key")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1a1a1a")
        self.new_key = None
        
        # Dimensiones y posición central
        w, h = 550, 400
        ws = self.root.winfo_screenwidth()
        hs = self.root.winfo_screenheight()
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2)
        self.root.geometry('%dx%d+%d+%d' % (w, h, x, y))

        # Fuentes
        title_font = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        msg_font = tkfont.Font(family="Segoe UI", size=11)
        btn_font = tkfont.Font(family="Segoe UI", size=11, weight="bold")

        # Contenedor
        frame = tk.Frame(self.root, bg="#1a1a1a", padx=30, pady=30)
        frame.pack(expand=True, fill="both")

        # Ícono / Título
        tk.Label(frame, text="🔑", font=("Segoe UI", 32), bg="#1a1a1a").pack()
        tk.Label(frame, text="OPENROUTER API KEY", font=title_font, bg="#1a1a1a", fg="#ffffff").pack(pady=(0, 10))

        # Mensaje de error
        if error_msg:
            tk.Label(frame, text=f"Estado actual: {error_msg}", font=msg_font, bg="#1a1a1a", fg="#e74c3c", wraplength=480).pack(pady=(0, 15))
        else:
            tk.Label(frame, text="Se requiere una API Key válida para el funcionamiento de la IA.", font=msg_font, bg="#1a1a1a", fg="#bdc3c7").pack(pady=(0, 15))

        tk.Label(frame, text="Pega tu nueva clave aquí:", font=msg_font, bg="#1a1a1a", fg="#ffffff").pack(anchor="w")
        
        self.entry = tk.Entry(frame, font=("Consolas", 10), bg="#2d2d2d", fg="#ffffff", insertbackground="white", relief="flat")
        self.entry.pack(fill="x", pady=(5, 20), ipady=8)
        self.entry.insert(0, current_key if current_key != "tu_api_key_aqui" else "")

        # Botones
        btn_frame = tk.Frame(frame, bg="#1a1a1a")
        btn_frame.pack(fill="x", pady=10)

        tk.Button(btn_frame, text="✅ VALIDAR Y GUARDAR", command=self.save,
                  font=btn_font, bg="#27ae60", fg="white", activebackground="#219150",
                  relief="flat", cursor="hand2", padx=20, pady=10).pack(side="right", padx=5)

        tk.Button(btn_frame, text="❌ CANCELAR", command=self.cancel,
                  font=btn_font, bg="#c0392b", fg="white", activebackground="#a93226",
                  relief="flat", cursor="hand2", padx=20, pady=10).pack(side="right", padx=5)

    def save(self):
        val = self.entry.get().strip()
        if not val:
            messagebox.showwarning("Campo vacío", "Por favor ingresa una clave válida.")
            return
        
        is_ok, msg = test_api_key(val)
        if is_ok:
            if update_env_key(val):
                self.new_key = val
                messagebox.showinfo("Éxito", "API Key actualizada y verificada correctamente.")
                self.root.destroy()
            else:
                messagebox.showerror("Error", "No se pudo guardar la clave en el archivo .env")
        else:
            messagebox.showerror("Clave Inválida", f"La clave proporcionada no es válida:\n{msg}")

    def cancel(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()
        return self.new_key

def main():
    # Cargar variables de entorno forzando recarga
    load_dotenv(str(ENV_PATH), override=True)
    current_key = os.getenv("OPENROUTER_API_KEY", "")
    
    print(f"Verificando API Key actual...")
    is_ok, msg = test_api_key(current_key)
    
    if is_ok:
        print(f"✅ OpenRouter API Key OK: {msg}")
        sys.exit(0)
    else:
        print(f"❌ Error en API Key: {msg}")
        
        # Notificar por Telegram
        try:
            enviar_alerta_todos(f"⚠️ <b>ALERTA DE SISTEMA</b> ⚠️\n\nLa API Key de OpenRouter ha fallado o no está configurada.\n<b>Error:</b> {msg}\n\nSe requiere intervención manual.")
        except:
            pass
        
        # Mostrar GUI
        win = KeyUpdateWindow(current_key, msg)
        new_key = win.run()
        
        if new_key:
            try:
                enviar_alerta_todos("✅ <b>SISTEMA RESTAURADO</b> ✅\n\nLa API Key de OpenRouter ha sido actualizada y verificada correctamente.")
            except:
                pass
            sys.exit(0)
        else:
            print("El usuario canceló la actualización.")
            sys.exit(1)

if __name__ == "__main__":
    main()
