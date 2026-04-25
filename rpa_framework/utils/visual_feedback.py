import time
import threading
import tkinter as tk
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class VisualFeedback:
    """
    Provee feedback visual en pantalla para acciones de RPA.
    - Resaltado de clicks (círculo rojo)
    - Mensajes de estado (overlay de texto)
    - Cuenta regresiva (countdown) para esperas
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        # Singleton thread-safe para facilitar acceso global si es necesario
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(VisualFeedback, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.message_window = None
        self.countdown_window = None
        self._persistent_windows = {}

    def highlight_click(self, x: int, y: int, color: str = "#ff0000", duration: float = 0.3):
        """
        Dibuja un círculo temporal en las coordenadas (x, y).
        Se ejecuta en un hilo separado para no bloquear la ejecución principal.
        """
        try:
            t = threading.Thread(target=self._draw_circle_thread, args=(x, y, color, duration), daemon=True)
            t.start()
        except Exception as e:
            logger.error(f"Error iniciando highlight_click: {e}")

    def highlight_region(self, x: int, y: int, width: int, height: int, color: str = "#ff0000", duration: float = 1.0):
        """
        Dibuja un rectángulo temporal en las coordenadas (x, y, w, h).
        """
        try:
            t = threading.Thread(target=self._draw_rect_thread, args=(x, y, width, height, color, duration), daemon=True)
            t.start()
        except Exception as e:
            logger.error(f"Error iniciando highlight_region: {e}")

    def _draw_circle_thread(self, x, y, color, duration):
        try:
            # Crear ventana sin bordes
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.7)  # Transparencia global
            
            # Posicionar centrada en el click
            size = 60
            offset = size // 2
            root.geometry(f"{size}x{size}+{int(x)-offset}+{int(y)-offset}")
            
            # Canvas
            # "white" será el color transparente
            canvas = tk.Canvas(root, width=size, height=size, bg='white', highlightthickness=0)
            canvas.pack()
            
            # Configurar color transparente para Windows
            try:
                root.wm_attributes("-transparentcolor", "white")
            except Exception:
                pass 
                
            # Dibujar círculo (anillo grueso) con el color especificado
            canvas.create_oval(4, 4, size-4, size-4, outline=color, width=4)
            # Opcional: un punto central
            canvas.create_oval(offset-2, offset-2, offset+2, offset+2, fill=color, outline=color)
            
            # Mostrar
            root.update()
            time.sleep(duration)
            
            # Fade out simple (opcional, si tkinter lo permite rápido)
            try:
                for alpha in [0.6, 0.4, 0.2, 0]:
                    root.attributes("-alpha", alpha)
                    root.update()
                    time.sleep(0.05)
            except:
                pass

            root.destroy()
        except Exception as e:
            logger.debug(f"Error dibujando círculo visual: {e}")

    def _draw_rect_thread(self, x, y, width, height, color, duration):
        try:
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.7)
            
            root.geometry(f"{width}x{height}+{int(x)}+{int(y)}")
            
            canvas = tk.Canvas(root, width=width, height=height, bg='white', highlightthickness=0)
            canvas.pack()
            
            try:
                root.wm_attributes("-transparentcolor", "white")
            except Exception:
                pass 
                
            # Dibujar rectángulo con el color especificado
            canvas.create_rectangle(2, 2, width-2, height-2, outline=color, width=4)
            
            root.update()
            time.sleep(duration)
            root.destroy()
        except Exception as e:
            logger.debug(f"Error dibujando rectángulo visual: {e}")

    def show_message(self, text: str, duration: float = 2.0):
        """
        Muestra un mensaje flotante (overlay) en la parte superior de la pantalla.
        """
        try:
            t = threading.Thread(target=self._show_message_thread, args=(text, duration), daemon=True)
            t.start()
        except Exception as e:
            logger.error(f"Error mostrando mensaje visual: {e}")

    def _show_message_thread(self, text, duration):
        try:
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.85)
            
            # Estilo
            bg_color = "#333333"
            fg_color = "#00FF00"  # Verde terminal
            font_style = ("Consolas", 12, "bold")
            
            label = tk.Label(root, text=text, bg=bg_color, fg=fg_color, font=font_style, padx=20, pady=10)
            label.pack()
            
            # Centrar en la parte superior
            root.update_idletasks()
            width = root.winfo_width()
            height = root.winfo_height()
            screen_width = root.winfo_screenwidth()
            
            x = (screen_width // 2) - (width // 2)
            y = 30  # 30px desde el tope
            
            root.geometry(f"{width}x{height}+{x}+{y}")
            root.update()
            
            time.sleep(duration)
            root.destroy()
        except Exception as e:
            logger.debug(f"Error en overlay de mensaje: {e}")

    def show_persistent_message(self, text: str, name: str, bg_color: str = "#333333", fg_color: str = "#FFFFFF"):
        """
        Muestra un mensaje que permanece hasta que se llama a hide_persistent_message.
        """
        try:
            # Si ya existe uno con ese nombre, cerrarlo
            self.hide_persistent_message(name)
            
            def _create():
                root = tk.Tk()
                root.overrideredirect(True)
                root.attributes("-topmost", True)
                root.attributes("-alpha", 0.9)
                
                font_style = ("Segoe UI", 12, "bold")
                
                # Crear un frame para el borde
                frame = tk.Frame(root, bg=bg_color, padx=2, pady=2)
                frame.pack()
                
                label = tk.Label(frame, text=text, bg=bg_color, fg=fg_color, font=font_style, padx=25, pady=12)
                label.pack()
                
                root.update_idletasks()
                width = root.winfo_width()
                height = root.winfo_height()
                screen_width = root.winfo_screenwidth()
                
                x = (screen_width // 2) - (width // 2)
                y = 50 # Un poco más abajo que los normales
                
                root.geometry(f"{width}x{height}+{x}+{y}")
                
                self._persistent_windows[name] = root
                root.mainloop()

            t = threading.Thread(target=_create, daemon=True)
            t.start()
            
            # Esperar un poco a que se cree
            timeout = 2.0
            start = time.time()
            while name not in self._persistent_windows and time.time() - start < timeout:
                time.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error mostrando mensaje persistente '{name}': {e}")

    def hide_persistent_message(self, name: str):
        """
        Oculta un mensaje persistente por su nombre.
        """
        try:
            if name in self._persistent_windows:
                root = self._persistent_windows.pop(name)
                root.after(0, root.destroy)
        except Exception as e:
            logger.error(f"Error ocultando mensaje persistente '{name}': {e}")

    def show_countdown(self, seconds: int, message: str = "Esperando..."):
        """
        Muestra una cuenta regresiva visual. Bloqueante visualmente (en su hilo), pero no detiene lógica si se usa en thread.
        NOTA: Para usarlo como reemplazo de sleep, llamar a wait()
        """
        try:
            t = threading.Thread(target=self._show_countdown_thread, args=(seconds, message), daemon=True)
            t.start()
        except Exception as e:
            logger.error(f"Error mostrando countdown: {e}")

    def _show_countdown_thread(self, seconds, message):
        try:
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.9)
            
            bg_color = "#FFF176" # Amarillo claro
            fg_color = "#E65100" # Naranja oscuro
            
            frame = tk.Frame(root, bg=bg_color, bd=2, relief="raised")
            frame.pack()
            
            lbl_msg = tk.Label(frame, text=message, bg=bg_color, fg="#333", font=("Arial", 10))
            lbl_msg.pack(pady=(5, 0))
            
            lbl_time = tk.Label(frame, text=f"{seconds}", bg=bg_color, fg=fg_color, font=("Arial", 24, "bold"))
            lbl_time.pack(pady=(0, 5))
            
            # Posición: Centro derecha o esquina superior izquierda
            root.update_idletasks()
            # w = root.winfo_width()
            # h = root.winfo_height()
            # x = 50
            # y = 50
            # root.geometry(f"+{x}+{y}")
            
            # Centrar en pantalla
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            x = (screen_width // 2) - (root.winfo_reqwidth() // 2)
            y = (screen_height // 2) - (root.winfo_reqheight() // 2)
            root.geometry(f"+{x}+{y}")

            for i in range(seconds, 0, -1):
                lbl_time.config(text=str(i))
                root.update()
                time.sleep(1)
            
            root.destroy()
        except Exception as e:
            logger.debug(f"Error en countdown: {e}")

    def wait(self, seconds: int, message: str = "Esperando"):
        """
        Reemplazo visual para time.sleep.
        Muestra countdown y bloquea el hilo actual.
        """
        if seconds <= 0: return
        
        # Iniciar visualización
        self.show_countdown(int(seconds), message)
        
        # Bloquear hilo actual
        time.sleep(seconds)

    def show_confirm(self, title: str, message: str, btn_yes: str = "Reintentar", btn_no: str = "Cancelar") -> bool:
        """
        Muestra un diálogo de confirmación personalizado.
        Retorna True si se presiona el botón Yes (Reintentar), False si No (Cancelar).
        Es bloqueante en el hilo que lo llama.
        """
        result = {"value": False}
        
        def _on_click(val):
            result["value"] = val
            root.destroy()

        root = tk.Tk()
        root.title(title)
        root.attributes("-topmost", True)
        
        # Estilo premium
        bg_color = "#2c3e50"
        fg_color = "#ecf0f1"
        btn_yes_color = "#27ae60"
        btn_no_color = "#c0392b"
        
        root.configure(bg=bg_color)
        root.overrideredirect(True) # Quitar bordes para que sea más premium
        
        # Centrar en pantalla
        root.update_idletasks()
        w, h = 400, 200
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = (sw // 2) - (w // 2)
        y = (sh // 2) - (h // 2)
        root.geometry(f"{w}x{h}+{x}+{y}")
        
        # Borde
        frame = tk.Frame(root, bg=bg_color, highlightbackground="#34495e", highlightthickness=2)
        frame.pack(fill="both", expand=True)
        
        tk.Label(frame, text=title, bg="#34495e", fg=fg_color, font=("Segoe UI", 12, "bold"), pady=10).pack(fill="x")
        
        tk.Label(frame, text=message, bg=bg_color, fg=fg_color, font=("Segoe UI", 10), pady=20, wraplength=350).pack()
        
        btn_frame = tk.Frame(frame, bg=bg_color, pady=10)
        btn_frame.pack()
        
        tk.Button(btn_frame, text=btn_yes, command=lambda: _on_click(True), 
                  bg=btn_yes_color, fg="white", font=("Segoe UI", 10, "bold"), 
                  padx=20, relief="flat", cursor="hand2").pack(side="left", padx=10)
        
        tk.Button(btn_frame, text=btn_no, command=lambda: _on_click(False), 
                  bg=btn_no_color, fg="white", font=("Segoe UI", 10, "bold"), 
                  padx=20, relief="flat", cursor="hand2").pack(side="left", padx=10)
        
        root.mainloop()
        return result["value"]

    def show_synonym_dialog(self, db_name: str, ocr_text: str) -> dict:
        """
        Muestra un diálogo enriquecido cuando falla la búsqueda OCR/LLM.
        Presenta:
          - El nombre que viene de la base de datos (examen buscado)
          - El texto que encontró el OCR (mejor candidato)
          - Un campo de texto para escribir un sinónimo / alternativa

        Retorna un dict con:
          {
            "action":   "save_retry"  → guardó sinónimo y reintenta
                        "retry"       → solo reintenta (sin sinónimo)
                        "cancel"      → cancela el proceso
            "synonym":  str | ""      → texto ingresado por el usuario
          }
        """
        result = {"action": "cancel", "synonym": ""}
        # Usamos lista mutable para que los callbacks accedan al widget entry
        # después de crearlo (evita el problema de StringVar sin root en Python 3.13)
        entry_ref = []

        def _on_save_retry():
            result["action"] = "save_retry"
            result["synonym"] = entry_ref[0].get().strip() if entry_ref else ""
            root.destroy()

        def _on_retry():
            result["action"] = "retry"
            result["synonym"] = ""
            root.destroy()

        def _on_cancel():
            result["action"] = "cancel"
            result["synonym"] = ""
            root.destroy()

        root = tk.Tk()
        root.title("⚠️ Búsqueda Fallida")
        root.attributes("-topmost", True)
        root.resizable(False, False)

        # Paleta de colores premium
        C_BG      = "#1e2733"
        C_PANEL   = "#263040"
        C_BORDER  = "#3a4a5e"
        C_TITLE   = "#f39c12"
        C_FG      = "#ecf0f1"
        C_DIM     = "#8899aa"
        C_TAG_BG  = "#2d3f55"
        C_INPUT   = "#0d1520"
        C_GREEN   = "#27ae60"
        C_BLUE    = "#2980b9"
        C_RED     = "#c0392b"

        root.configure(bg=C_BG)
        root.overrideredirect(True)

        # Tamaño y centrado
        W, H = 520, 400
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = (sw // 2) - (W // 2)
        y = (sh // 2) - (H // 2)
        root.geometry(f"{W}x{H}+{x}+{y}")

        # ─── Barra de título personalizada ───────────────────────────────────
        title_bar = tk.Frame(root, bg="#c0392b", height=40)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)

        tk.Label(
            title_bar,
            text="  ⚠️  Búsqueda Fallida — Gestión de Sinónimos",
            bg="#c0392b", fg="white",
            font=("Segoe UI", 10, "bold"),
            anchor="w"
        ).pack(side="left", padx=8, fill="y")

        # ─── Cuerpo principal ─────────────────────────────────────────────────
        body = tk.Frame(root, bg=C_BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)

        def _label_row(parent, tag, value, tag_color=C_TITLE):
            row = tk.Frame(parent, bg=C_BG)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=tag, bg=C_TAG_BG, fg=tag_color,
                     font=("Segoe UI", 8, "bold"),
                     width=14, anchor="center", relief="flat",
                     padx=4, pady=2).pack(side="left")
            tk.Label(row, text=value or "(sin texto)", bg=C_PANEL, fg=C_FG,
                     font=("Consolas", 9),
                     wraplength=340, anchor="w", justify="left",
                     padx=8, pady=4, relief="flat").pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Examen buscado (BD)
        _label_row(body, "  BD (buscado)", db_name, C_TITLE)

        # Texto OCR encontrado
        _label_row(body, "  OCR (encontrado)", ocr_text if ocr_text else "—  (no se encontró texto)", C_BLUE)

        # Separador
        tk.Frame(body, bg=C_BORDER, height=1).pack(fill="x", pady=10)

        # Instrucción
        tk.Label(
            body,
            text="💡  Escribe un sinónimo o nombre alternativo del examen\n"
                 "    para buscarlo nuevamente en el PACS:",
            bg=C_BG, fg=C_DIM,
            font=("Segoe UI", 9),
            justify="left", anchor="w"
        ).pack(fill="x", pady=(0, 6))

        # Campo de entrada (sin StringVar para compatibilidad Python 3.13+)
        entry_frame = tk.Frame(body, bg=C_BORDER, pady=1, padx=1)
        entry_frame.pack(fill="x")
        entry = tk.Entry(
            entry_frame,
            bg=C_INPUT, fg=C_FG,
            insertbackground=C_FG,
            font=("Segoe UI", 11),
            relief="flat", bd=6
        )
        entry.pack(fill="x")
        entry_ref.append(entry)   # guardar referencia para los callbacks
        entry.focus_set()
        # Enter = Guardar y reintentar
        entry.bind("<Return>", lambda _e: _on_save_retry())

        # ─── Botones ──────────────────────────────────────────────────────────
        tk.Frame(body, bg=C_BORDER, height=1).pack(fill="x", pady=10)

        btn_frame = tk.Frame(body, bg=C_BG)
        btn_frame.pack()

        def _btn(parent, text, cmd, color, width=16):
            b = tk.Button(
                parent, text=text, command=cmd,
                bg=color, fg="white",
                font=("Segoe UI", 9, "bold"),
                relief="flat", cursor="hand2",
                width=width, pady=6,
                activebackground=color, activeforeground="white"
            )
            b.pack(side="left", padx=5)
            return b

        _btn(btn_frame, "💾 Guardar y Reintentar", _on_save_retry, C_GREEN, 20)
        _btn(btn_frame, "🔄 Solo Reintentar",      _on_retry,      C_BLUE,  16)
        _btn(btn_frame, "❌ Cancelar",             _on_cancel,     C_RED,   12)

        root.mainloop()
        return result

