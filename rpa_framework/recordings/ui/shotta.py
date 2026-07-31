#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: shotta
Generado: 2026-07-07 18:47:19
Total de acciones: 3
"""

import sys
import time
import logging
import threading
import tkinter as tk
import pyautogui
from pathlib import Path
from datetime import datetime

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pywinauto import Application, findwindows
from utils.logging_setup import setup_logging

# Definición local para evitar dependencias del executor
class ActionType:
    CLICK = "click"
    DOUBLE_CLICK = "double_click"

class Action:
    def __init__(self, type, selector=None, position=None, timestamp=None, app_context=None):
        self.type = type
        self.selector = selector
        self.position = position
        self.timestamp = timestamp
        self.app_context = app_context

# Configuración de MySQL (opcional)
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logger = logging.getLogger(__name__)

class VisualFeedbackLocal:
    """Feedback visual integrado para ser independiente del framework."""
    def highlight_click(self, x, y, color="#FF0000", duration=0.5):
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

    def show_banner(self, text, duration=1.5):
        try:
            t = threading.Thread(target=self._draw_banner, args=(text, duration), daemon=True)
            t.start()
        except: pass

    def _draw_banner(self, text, duration):
        try:
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            screen_width = root.winfo_screenwidth()
            root.geometry(f"650x60+{int(screen_width/2)-325}+40")
            root.configure(bg="#2C3E50")
            
            label = tk.Label(root, text=text, fg="#F1C40F", bg="#2C3E50", font=("Arial", 14, "bold"), bd=2, relief="ridge")
            label.pack(expand=True, fill='both')
            
            root.update()
            time.sleep(duration)
            root.destroy()
        except: pass

vf = VisualFeedbackLocal()


class ShottaAutomation:
    """Automatización generada: shotta"""
    
    def __init__(self):
        self.app = None
        self.executor = None
        self.main_window = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.matched_image_box = None
        
    def db_update_status(self, status='En Proceso'):
        """Actualiza el estado en la BD"""
        if not HAS_MYSQL:
            return
        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            script_name = "shotta"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
            logger.info(f"[DB] Tracking actualizado: {script_name} ({status})")
        except Exception as e:
            logger.warning(f"[DB Error] {e}")

    def humanized_click(self, x, y, duration=0.5, is_double=False, element=None):
        """Mueve el mouse, resalta y realiza el clic con reintentos y métodos redundantes para clics difíciles."""
        logger.info(f"Posicionando mouse en ({x}, {y}) para clic {'doble' if is_double else 'sostenido' if duration > 0 else 'simple'}...")
        
        # Mover mouse suavemente
        pyautogui.moveTo(x, y, duration=0.3, tween=pyautogui.easeInOutQuad)
        time.sleep(0.1)
        
        if vf:
            vf.highlight_click(x, y, color="#FF0000", duration=0.5)
            time.sleep(0.1)

        # Si tenemos el elemento de pywinauto, intentamos clic nativo primero
        if element:
            # 1. Intentar invoke() de la API de UIA (funciona sin importar el mouse o foco)
            try:
                logger.info("Intentando invoke() UIA...")
                element.invoke()
                time.sleep(0.3)
                logger.info("Invoke UIA exitoso")
                return
            except Exception as e:
                logger.debug(f"No se pudo invocar elemento: {e}")

            # 2. Intentar click_input() nativo de pywinauto
            try:
                logger.info("Intentando clic nativo sobre el control con pywinauto...")
                if is_double:
                    element.double_click_input()
                elif duration > 0:
                    element.press_mouse_input()
                    time.sleep(duration)
                    element.release_mouse_input()
                else:
                    element.click_input()
                time.sleep(0.3)
                logger.info("Clic nativo completado con éxito")
                return
            except Exception as e:
                logger.warning(f"Fallo clic nativo con pywinauto ({e}), usando fallback físico...")

        # Fallback físico robusto con pywinauto.mouse (envía eventos del sistema)
        try:
            from pywinauto import mouse
            logger.info("Ejecutando clic físico usando pywinauto.mouse...")
            if is_double:
                mouse.double_click(coords=(x, y))
            elif duration > 0:
                mouse.press(coords=(x, y))
                time.sleep(duration)
                mouse.release(coords=(x, y))
            else:
                mouse.click(coords=(x, y))
            time.sleep(0.3)
            logger.info("Clic físico con pywinauto.mouse completado")
            return
        except Exception as e:
            logger.warning(f"Fallo pywinauto.mouse ({e}), usando fallback final de pyautogui...")

        # Fallback final con pyautogui y pulsación de teclado ENTER
        try:
            if is_double:
                pyautogui.doubleClick(x, y)
            elif duration > 0:
                pyautogui.mouseDown(x, y)
                time.sleep(duration)
                pyautogui.mouseUp(x, y)
            else:
                pyautogui.click(x, y)
            time.sleep(0.3)
            logger.info("Clic físico con pyautogui completado")
            
            # Refuerzo por teclado para diálogos que puedan estar bloqueados
            logger.info("Enviando ENTER por teclado como refuerzo para el diálogo...")
            pyautogui.press('enter')
            time.sleep(0.2)
        except Exception as e:
            logger.error(f"Error crítico en todos los intentos de clic: {e}")
            raise e

    def find_element_local(self, selector, timeout=2.0):
        """Busca el elemento directamente en el Desktop (global) para diálogos modales o en ventana principal."""
        from pywinauto import Desktop
        
        if "position" in selector:
            pos_data = selector["position"]
            if isinstance(pos_data, dict):
                x, y = pos_data["x"], pos_data["y"]
            else:
                x, y = pos_data[0], pos_data[1]
            try:
                return Desktop(backend='uia').from_point(x, y)
            except Exception as e:
                logger.warning(f"No se pudo obtener elemento por punto ({x}, {y}): {e}")
                return None

        kwargs = {}
        if "automation_id" in selector:
            kwargs["auto_id"] = selector["automation_id"]
        if "name" in selector:
            kwargs["title"] = selector["name"]
        if "title_re" in selector:
            kwargs["title_re"] = selector["title_re"]
        if "control_type" in selector:
            kwargs["control_type"] = selector["control_type"]
        if "class_name" in selector:
            kwargs["class_name"] = selector["class_name"]

        if not kwargs:
            return None

        # Intentar buscar en Desktop (global) primero, luego en main_window y app
        for root_win in [Desktop(backend='uia'), self.main_window, self.app]:
            if root_win is None:
                continue
            try:
                element = root_win.child_window(**kwargs)
                element.wait("exists enabled visible", timeout=1.0)
                logger.info(f"Elemento UIA localizado exitosamente en raíz {root_win}")
                return element
            except:
                pass
        return None



    def ensure_active_window(self):
        try:
            top_win = self.app.top_window()
            hwnd = top_win.handle
            
            import win32gui
            import win32con
            
            # Restaurar si está minimizada
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            
            # Traer al frente
            win32gui.SetForegroundWindow(hwnd)
            win32gui.SetActiveWindow(hwnd)
            time.sleep(0.3)
        except Exception as e:
            logger.debug(f"Error forzando foco de top_window con win32gui: {e}")
            if self.main_window:
                try:
                    self.main_window.set_focus()
                    time.sleep(0.25)
                except:
                    pass

    def is_dialog_still_open(self):
        # 1. Comprobación por árbol de ventanas (inmune a que la ventana esté tapada por otra app)
        w, btn = self.find_dialog_and_button_uia()
        if w is not None:
            logger.info("El diálogo sigue abierto (detectado en el árbol de ventanas de Windows).")
            return True

        # 2. Comprobación visual como fallback
        root_dir = Path(__file__).parent.parent.parent
        image_paths = [
            str(root_dir / "utils" / "shotta.png"),
            str(root_dir / "utils" / "shotta zoom.png")
        ]
        for img_path in image_paths:
            if Path(img_path).exists():
                try:
                    if pyautogui.locateOnScreen(img_path, confidence=0.8) is not None:
                        logger.info(f"El diálogo sigue abierto (detectado visualmente por {Path(img_path).name}).")
                        return True
                except:
                    pass
        return False

    def find_dialog_and_button_uia(self):
        """Busca el diálogo modal 'Carestream Client' (clase #32770) y el botón Aceptar."""
        from pywinauto import Desktop
        
        # 1. Búsqueda directa por clase #32770 (MessageBox estándar de Windows) con pywinauto UIA
        try:
            desktop_uia = Desktop(backend='uia')
            for w in desktop_uia.windows():
                try:
                    cn = w.class_name()
                    wt = w.window_text()
                    # El diálogo es un #32770 con título "Carestream Client"
                    if cn == "#32770" or "WindowsForms" in cn or wt == "":
                        btn = w.child_window(title="Aceptar", control_type="Button")
                        if btn.exists(timeout=0.3):
                            logger.info(f"Diálogo modal detectado (UIA): '{wt}' (Class: {cn})")
                            return w, btn
                except:
                    pass
        except Exception as e:
            logger.debug(f"Error buscando con backend UIA: {e}")

        # 2. Fallback con backend Win32
        try:
            desktop_win32 = Desktop(backend='win32')
            for w in desktop_win32.windows():
                try:
                    cn = w.class_name()
                    wt = w.window_text()
                    if cn == "#32770" or "WindowsForms" in cn or wt == "":
                        btn = w.child_window(title="Aceptar")
                        if btn.exists(timeout=0.3):
                            logger.info(f"Diálogo modal detectado (Win32): '{wt}' (Class: {cn})")
                            return w, btn
                except:
                    pass
        except Exception as e:
            logger.debug(f"Error buscando con backend Win32: {e}")
            
        return None, None

    def direct_win32_click(self):
        """Busca el botón Aceptar por win32gui.EnumChildWindows y envía BM_CLICK directamente al hwnd."""
        import win32gui
        import win32con
        import win32process
        
        # 1. Encontrar el diálogo #32770 con título "Carestream Client"
        dialog_hwnd = None
        all_windows = []
        def enum_cb(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                results.append(hwnd)
        win32gui.EnumWindows(enum_cb, all_windows)
        
        for hwnd in all_windows:
            try:
                title = win32gui.GetWindowText(hwnd)
                cls = win32gui.GetClassName(hwnd)
                if cls == "#32770" and "Carestream" in title:
                    dialog_hwnd = hwnd
                    logger.info(f"Diálogo #32770 encontrado: hwnd={hwnd}, título='{title}'")
                    break
            except:
                pass
        
        if not dialog_hwnd:
            logger.warning("No se encontró diálogo #32770 de Carestream.")
            return False
        
        # 2. Encontrar el botón Aceptar como hijo del diálogo
        btn_hwnd = None
        child_wins = []
        def enum_child_cb(hwnd, results):
            results.append(hwnd)
        try:
            win32gui.EnumChildWindows(dialog_hwnd, enum_child_cb, child_wins)
        except:
            pass
        
        for chwnd in child_wins:
            try:
                text = win32gui.GetWindowText(chwnd)
                if "aceptar" in text.lower() or text == "OK" or text == "&Aceptar":
                    btn_hwnd = chwnd
                    logger.info(f"Botón '{text}' encontrado: hwnd={chwnd}")
                    break
            except:
                pass
        
        if not btn_hwnd:
            logger.warning("No se encontró el botón Aceptar como hijo del diálogo.")
            return False
        
        # 3. Sincronizar hilos de entrada (AttachThreadInput) para permitir el envío de mensajes
        try:
            import ctypes
            current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            target_thread, _ = win32process.GetWindowThreadProcessId(dialog_hwnd)
            ctypes.windll.user32.AttachThreadInput(current_thread, target_thread, True)
            
            # Traer al frente y dar foco
            win32gui.SetForegroundWindow(dialog_hwnd)
            win32gui.SetFocus(btn_hwnd)
            time.sleep(0.3)
            
            # Enviar BM_CLICK directamente al botón
            logger.info(f"Enviando BM_CLICK al botón (hwnd={btn_hwnd})...")
            win32gui.SendMessage(btn_hwnd, win32con.BM_CLICK, 0, 0)
            time.sleep(0.5)
            
            # Desconectar hilos
            ctypes.windll.user32.AttachThreadInput(current_thread, target_thread, False)
            return True
        except Exception as e:
            logger.warning(f"Error en direct_win32_click: {e}")
            return False



    def dump_uia_tree(self):
        """Vuelca la jerarquía UIA de la ventana superior activa y lista ventanas del escritorio."""
        try:
            logger.info("=== VOLCANDO ESTRUCTURA DE CONTROLES UIA DE LA VENTANA ACTIVA ===")
            top_win = self.app.top_window()
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                top_win.print_control_identifiers()
            logger.info(f.getvalue())
            logger.info("=== FIN DE ESTRUCTURA UIA ===")
        except Exception as e:
            logger.warning(f"No se pudo volcar la jerarquía UIA de la ventana superior: {e}")

        try:
            from pywinauto import Desktop
            logger.info("=== VENTANAS DE PRIMER NIVEL DETECTADAS EN EL ESCRITORIO ===")
            for win in Desktop(backend='uia').windows():
                logger.info(f"Ventana: '{win.window_text()}' | Clase: '{win.class_name()}' | ProcessID: {win.process_id()}")
            logger.info("=== FIN DE VENTANAS DEL ESCRITORIO ===")
        except Exception as e:
            logger.warning(f"No se pudo listar ventanas del escritorio: {e}")

    def execute_click_action(self, action):
        """Ejecuta un clic resolviendo primero las coordenadas si es un selector."""
        x, y = None, None
        element = None
        
        self.ensure_active_window()
        self.dump_uia_tree()
        
        # Clic de enfoque en la barra de título del diálogo para asegurar foco físico
        if self.matched_image_box:
            logger.info("Haciendo clic en la barra de título del diálogo para asegurar foco...")
            pyautogui.click(self.matched_image_box.left + 100, self.matched_image_box.top + 15)
            time.sleep(0.4)

        # Intentar localizar el control UIA de forma global
        if action.selector:
            element = self.find_element_local(action.selector, timeout=2.0)
            if element:
                try:
                    try:
                        element.set_focus()
                        time.sleep(0.2)
                    except:
                        pass
                    rect = element.rectangle()
                    x, y = rect.mid_point().x, rect.mid_point().y
                except Exception as e:
                    logger.warning(f"Error al obtener coordenadas del elemento UIA: {e}")
                    element = None

        if x is None or y is None:
            # 1. Intentar localizar por imagen recortada btn_aceptar.png dentro del diálogo matched_image_box
            btn_img = r"c:\Desarrollo\RPA_3\rpa_framework\utils\btn_aceptar.png"
            img_coords_found = False
            if self.matched_image_box:
                try:
                    logger.info(f"Buscando coordenadas exactas del botón '{btn_img}' usando template matching...")
                    pos = pyautogui.locateCenterOnScreen(btn_img, region=self.matched_image_box, confidence=0.8)
                    if pos:
                        x, y = pos
                        logger.info(f"Coordenadas del botón encontradas de forma exacta por imagen: ({x}, {y})")
                        img_coords_found = True
                except Exception as e:
                    logger.warning(f"Error al localizar el botón por imagen en matched_image_box: {e}")

            # 2. Fallback a calcular el centro estimado del diálogo
            if not img_coords_found and self.matched_image_box:
                x = int(self.matched_image_box.left + (self.matched_image_box.width / 2))
                y = int(self.matched_image_box.top + 123)
                logger.info(f"Usando coordenadas dinámicas relativas (centro estimado): ({x}, {y})")
            elif not img_coords_found and action.position and "x" in action.position and "y" in action.position:
                x, y = action.position["x"], action.position["y"]
            elif not img_coords_found:
                raise Exception("No hay selector válido ni coordinates para el clic")

        # Estrategia comprobada: directo al hwnd del botón usando Win32 API
        strategies = [
            {
                "id": 0,
                "name": "Win32 DirectClick (hwnd #32770 + BM_CLICK + AttachThreadInput)",
                "action": lambda: self.direct_win32_click()
            }
        ]

        success_strategy = None
        for idx, strategy in enumerate(strategies):
            banner_text = f"Estrategia {strategy['id']}: {strategy['name']}"
            logger.info(f"=== Intentando {banner_text} ===")
            if vf:
                vf.show_banner(f"Intentando {banner_text}...", duration=2.0)
                time.sleep(2.0)

            self.ensure_active_window()

            # Resaltar en pantalla
            if vf:
                vf.highlight_click(x, y, color="#FF9900", duration=0.8)
                time.sleep(0.2)

            try:
                strategy["action"]()
                time.sleep(1.5) # Esperar a ver si responde o se cierra

                # Verificar si el diálogo se cerró
                if not self.is_dialog_still_open():
                    success_strategy = strategy
                    success_msg = f"¡ÉXITO! Estrategia {strategy['id']} ({strategy['name']}) FUNCIONÓ"
                    logger.info(f"✅ {success_msg}")
                    if vf:
                        vf.show_banner(success_msg, duration=3.0)
                        time.sleep(3.0)
                    break
                else:
                    logger.warning(f"❌ Estrategia {strategy['id']} no cerró el diálogo.")
            except Exception as ex:
                logger.warning(f"❌ Error en estrategia {strategy['id']} ({strategy['name']}): {ex}")

        if not success_strategy:
            logger.error("❌ Ninguna de las estrategias pudo cerrar el diálogo.")
            raise Exception("Set de pruebas de clics fallido")

        # Petición: Después del clic, seleccionar la ventana de Philips Workflow Information Management
        logger.info("Buscando y seleccionando la ventana de Philips Workflow Information Management...")
        try:
            import win32gui
            import win32con
            
            def enum_philips_cb(hwnd, results):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if "Philips Workflow Information Management" in title or "Workflow Information Management" in title:
                        results.append(hwnd)
                        
            found_hwnds = []
            win32gui.EnumWindows(enum_philips_cb, found_hwnds)
            
            if found_hwnds:
                philips_hwnd = found_hwnds[0]
                title = win32gui.GetWindowText(philips_hwnd)
                logger.info(f"Ventana encontrada: '{title}' (hwnd={philips_hwnd})")
                
                if win32gui.IsIconic(philips_hwnd):
                    win32gui.ShowWindow(philips_hwnd, win32con.SW_RESTORE)
                
                win32gui.ShowWindow(philips_hwnd, win32con.SW_SHOW)
                win32gui.SetForegroundWindow(philips_hwnd)
                logger.info("✅ Ventana de Philips Workflow traída al primer plano con éxito.")
            else:
                logger.warning("No se encontró la ventana de Philips Workflow Information Management.")
        except Exception as e:
            logger.warning(f"Error al intentar enfocar Philips Workflow: {e}")

    def bring_app_to_foreground(self) -> bool:
        """Busca las ventanas conocidas del cliente Carestream y las trae al primer plano."""
        target_title = ".*(Carestream RIS|Workflow Information Management|Carestream RIS V11|Carestream Vue PACS|Vue PACS|Carestream Client|Carestream Radiology Client).*"
        logger.info(f"Intentando traer al primer plano la aplicación que coincida con: {target_title}")
        try:
            titulos = findwindows.find_elements(title_re=target_title)
            if titulos:
                hwnd = titulos[0].handle
                import win32gui
                import win32con
                
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.5)
                logger.info(f"Ventana '{titulos[0].name}' puesta en primer plano.")
                return True
            else:
                logger.warning("No se encontró ninguna ventana que coincida con los criterios para traer al frente.")
        except Exception as e:
            logger.warning(f"No se pudo traer la aplicación al primer plano: {e}")
        return False

    def setup(self) -> bool:
        """Conecta a la aplicación objetivo de forma robusta."""
        logger.info("Configurando conexión a la aplicación...")
        
        try:
            # Estrategia de conexión robusta con reintentos para Carestream RIS / PACS
            target_title = ".*(Carestream RIS|Workflow Information Management|Carestream RIS V11|Carestream Vue PACS|Vue PACS|Carestream Client|Carestream Radiology Client).*"
            connected = False
            
            for attempt in range(1, 4):
                try:
                    logger.debug(f"Intento {attempt} de conexión a {target_title}...")
                    # 1. Buscar por título para obtener un handle estable
                    titulos = findwindows.find_elements(title_re=target_title, backend='uia')
                    
                    if titulos:
                        logger.info(f"Ventana encontrada por título: {titulos[0].name}")
                        self.app = Application(backend='uia').connect(handle=titulos[0].handle)
                    else:
                        # 2. Fallback a conectar por process path o title_re directo
                        try:
                            self.app = Application(backend='uia').connect(path="Carestream RIS.exe")
                        except:
                            self.app = Application(backend='uia').connect(title_re=target_title)
                    
                    # 3. Validar existencia y dar foco
                    self.main_window = self.app.window(title_re=target_title)
                    if self.main_window.exists(timeout=5):
                        self.main_window.set_focus()
                        time.sleep(0.5)
                        self.main_window.set_focus() # Segundo foco para asegurar
                        connected = True
                        break
                    else:
                        logger.warning(f"Intento {attempt}: La ventana no parece estar lista")
                except Exception as connect_e:
                    logger.warning(f"Intento {attempt} fallido: {connect_e}")
                    time.sleep(1)
            
            if not connected:
                # Fallback final a Desktop
                logger.warning("No se pudo conectar a la ventana específica, usando Desktop como root")
                self.app = Application(backend='uia')
                self.main_window = None
            
            self.executor = None
            logger.info("✅ Conexión establecida")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en setup: {e}")
            return False
    
    def run(self) -> dict:
        """Ejecuta todas las acciones grabadas."""
        results = {
            "session_id": self.session_id,
            "status": "SKIPPED",
            "total_actions": 1,
            "completed": 0,
            "failed": 0,
            "errors": [],
            "start_time": datetime.now().isoformat(),
        }
        
        # Traer la aplicación al frente antes de buscar imágenes
        self.bring_app_to_foreground()
        
        logger.info("Buscando 'shotta.png' o 'shotta zoom.png' en pantalla...")
        
        root_dir = Path(__file__).parent.parent.parent
        image_paths = [
            str(root_dir / "utils" / "shotta.png"),
            str(root_dir / "utils" / "shotta zoom.png")
        ]
        
        found = False
        for img_path in image_paths:
            if not Path(img_path).exists():
                logger.warning(f"Imagen de referencia no encontrada: {img_path}")
                continue
            try:
                # 80% de similitud para tolerar pequeñas variaciones
                location = pyautogui.locateOnScreen(img_path, confidence=0.8)
                if location is not None:
                    logger.info(f"Coincidencia encontrada con {img_path} en {location}")
                    self.matched_image_box = location
                    found = True
                    break
            except Exception as e:
                logger.debug(f"Error o no encontrada la imagen {img_path}: {e}")
                
        if not found:
            logger.info("No se detectó similitud con las imágenes requeridas. No se realiza ninguna acción.")
            results["end_time"] = datetime.now().isoformat()
            return results

        # Si se encuentra, procede con el resto (setup y acciones)
        if not self.setup():
            results["status"] = "FAILED"
            results["errors"].append({"reason": "Setup failed"})
            results["end_time"] = datetime.now().isoformat()
            return results
            
        results["status"] = "RUNNING"
        
        logger.info(f"🚀 Iniciando ejecución: {results['total_actions']} acciones")
        
        # DB Tracking: Start
        self.db_update_status('En Proceso')
        
        try:
            # Acción 1: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Aceptar', 'control_type': 'Button'},
                    position={'x': 969, 'y': 576},
                    timestamp=datetime.fromisoformat("2026-07-07T18:47:06.680093")
                )
                self.execute_click_action(action)
                results["completed"] += 1
                logger.info(f"[1/3] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "click", "reason": str(e)})
                logger.error(f"[1/3] ❌ click: {e}")

            results["status"] = "SUCCESS" if results["failed"] == 0 else "PARTIAL"
            
        except Exception as e:
            logger.error(f"❌ Error crítico: {e}")
            results["status"] = "FAILED"
            results["errors"].append({"reason": str(e)})
            self.db_update_status('error')
        
        results["end_time"] = datetime.now().isoformat()
        
        logger.info(f"📊 RESUMEN: {results['completed']} OK, {results['failed']} FAILED")
        logger.info(f"Status: {results['status']}")
        
        # DB Tracking: Final
        if results["status"] == "SUCCESS":
            self.db_update_status('En Proceso')
        
        return results


def main():
    """Punto de entrada principal."""
    setup_logging()
    
    automation = ShottaAutomation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/{results['total_actions']}")
    print(f"Fallidas: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] in ["SUCCESS", "SKIPPED"] else 1


if __name__ == "__main__":
    sys.exit(main())
