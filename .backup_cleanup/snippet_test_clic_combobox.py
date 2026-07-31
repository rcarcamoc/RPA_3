import sys
import time
import logging
import threading
import tkinter as tk
import pyautogui
from pywinauto import Application, findwindows

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VisualFeedbackLocal:
    def show_message(self, text, duration=1.0):
        def _show():
            try:
                root = tk.Tk()
                root.overrideredirect(True)
                root.attributes("-topmost", True)
                label = tk.Label(root, text=text, bg="#333333", fg="#00FF00", font=("Consolas", 14, "bold"), padx=20, pady=10)
                label.pack()
                root.update_idletasks()
                x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
                root.geometry(f"+{x}+30")
                root.update()
                time.sleep(duration)
                root.destroy()
            except Exception as e:
                pass
        threading.Thread(target=_show, daemon=True).start()

    def highlight_click(self, x, y, color="#FF0000", duration=0.8):
        try:
            t = threading.Thread(target=self._draw_circle, args=(x, y, color, duration), daemon=True)
            t.start()
        except: pass

    def _draw_circle(self, x, y, color, duration):
        try:
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.7)
            size = 60
            root.geometry(f"{size}x{size}+{int(x)-30}+{int(y)-30}")
            canvas = tk.Canvas(root, width=size, height=size, bg='white', highlightthickness=0)
            canvas.pack()
            try: root.wm_attributes("-transparentcolor", "white")
            except: pass
            canvas.create_oval(4, 4, size-4, size-4, outline=color, width=5)
            canvas.create_oval(28, 28, 32, 32, fill=color, outline=color)
            root.update()
            time.sleep(duration)
            root.destroy()
        except: pass

vf = VisualFeedbackLocal()

def humanized_click(x, y, duration=0.6):
    """Mueve, resalta con círculo rojo y hace clic sostenido."""
    logger.info(f"Posicionando mouse en ({x}, {y}) para clic...")
    pyautogui.moveTo(x, y, duration=0.4, tween=pyautogui.easeInOutQuad)
    time.sleep(0.1)
    
    vf.highlight_click(x, y, color="#FF0000", duration=0.8)
    time.sleep(0.2)
        
    pyautogui.mouseDown()
    time.sleep(duration)
    pyautogui.mouseUp()
    time.sleep(0.2)

def setup_app():
    target_title = ".*Carestream RIS V11.*"
    app = None
    main_window = None
    connected = False
    
    for attempt in range(1, 4):
        try:
            logger.info(f"Intento {attempt} de conexión a {target_title}...")
            titulos = findwindows.find_elements(title_re=target_title, backend='uia')
            if titulos:
                app = Application(backend='uia').connect(handle=titulos[0].handle)
            else:
                try:
                    app = Application(backend='uia').connect(path="Carestream RIS.exe")
                except:
                    app = Application(backend='uia').connect(title_re=target_title)
            
            main_window = app.window(title_re=target_title)
            if main_window.exists(timeout=5):
                main_window.set_focus()
                connected = True
                break
        except Exception as e:
            logger.warning(f"Intento {attempt} fallido: {e}")
            time.sleep(1)
            
    if not connected:
        logger.warning("Fallo en la conexión. Asegúrate de tener la ventana de Carestream abierta.")
        sys.exit(1)
        
    return main_window

def main():
    logger.info("Conectando a ventana...")
    main_window = setup_app()
    logger.info("Conectado exitosamente. Esperando 2 segundos...")
    time.sleep(2)

    logger.info("\n=== ALTERNATIVA 1: Pywinauto Native Click ===")
    vf.show_message("Alt 1: Pywinauto Nativo", duration=1.5)
    try:
        element_diag = main_window.child_window(auto_id='cbxClCodigodiagnostico1', control_type="ComboBox")
        if element_diag.exists(timeout=3):
            element_diag.click_input()
            logger.info("✅ Clic Nativo ejecutado")
        else:
            logger.warning("❌ No se encontró elemento cbxClCodigodiagnostico1")
    except Exception as e:
        logger.error(f"Error en Alt 1: {e}")

    logger.info("\nEsperando 4 segundos para el siguiente clic...")
    time.sleep(4)

    logger.info("\n=== ALTERNATIVA 2: Humanized Click usando coords del elemento ===")
    vf.show_message("Alt 2: Clic Flecha Lateral Elemento", duration=1.5)
    try:
        element_diag = main_window.child_window(auto_id='cbxClCodigodiagnostico1', control_type="ComboBox")
        if element_diag.exists(timeout=3):
            rect = element_diag.rectangle()
            x = rect.right - 15
            y = rect.mid_point().y
            humanized_click(x, y)
            logger.info(f"✅ Clic en ({x}, {y}) ejecutado")
        else:
            logger.warning("❌ No se encontró elemento cbxClCodigodiagnostico1")
    except Exception as e:
        logger.error(f"Error en Alt 2: {e}")

    logger.info("\nEsperando 4 segundos para el siguiente clic...")
    time.sleep(4)

    logger.info("\n=== ALTERNATIVA 3: Humanized Click Hardcoded Fallback (608, 192) ===")
    vf.show_message("Alt 3: Clic Coordenadas (608, 192)", duration=1.5)
    try:
        humanized_click(608, 192)
        logger.info("✅ Clic fallback ejecutado")
    except Exception as e:
        logger.error(f"Error en Alt 3: {e}")

    logger.info("\nPrueba finalizada.")

if __name__ == "__main__":
    main()
