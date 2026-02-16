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

