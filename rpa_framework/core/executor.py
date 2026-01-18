"""ActionExecutor - Ejecuta acciones con retry."""
import logging
import time
from typing import Callable
from functools import wraps
from pywinauto import Application
from .action import Action, ActionType
from .selector import WindowsSelector

logger = logging.getLogger(__name__)

def log_execution_time(func: Callable) -> Callable:
    """Decorator para loguear tiempo."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            logger.info(f"{func.__name__} completado en {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"{func.__name__} falló en {elapsed:.2f}s: {e}")
            raise
    return wrapper

class ActionExecutor:
    """Ejecuta acciones con retry y validación."""
    
    def __init__(self, app: Application, config: dict):
        self.app = app
        self.config = config
        self.selector_helper = WindowsSelector(
            app_context=config.get("app_context", "unknown"),
            max_retries=1, # Fail fast internal, let executor handle retries/fallback
            app=self.app
        )
    
    @log_execution_time
    def execute(self, action: Action) -> bool:
        """Ejecuta una acción según su tipo."""
        
        if action.wait_before > 0:
            logger.debug(f"Esperando {action.wait_before}s...")
            time.sleep(action.wait_before)
        
        if action.type == ActionType.CLICK:
            return self._execute_click(action)
        elif action.type == ActionType.DOUBLE_CLICK:
            return self._execute_double_click(action)
        elif action.type == ActionType.TYPE_TEXT:
            return self._execute_type_text(action)
        elif action.type == ActionType.KEY_PRESS:
            return self._execute_key_press(action)
        elif action.type == ActionType.KEY_COMBINATION:
            return self._execute_key_combination(action)
        elif action.type == ActionType.WAIT:
            return self._execute_wait(action)
        elif action.type == ActionType.VALIDATE:
            return self._execute_validate(action)
        else:
            logger.warning(f"Tipo desconocido: {action.type}")
            return False
    
    def _execute_click(self, action: Action) -> bool:
        """Click con fallback."""
        max_retries = self.config.get("click_retries", 2)
        retry_delay = self.config.get("retry_delay", 1.0)
        
        for attempt in range(1, max_retries + 1):
            try:
                if action.selector:
                    element = self.selector_helper.find_element(
                        action.selector,
                        timeout=self.config.get("element_timeout", 2.0),
                        app_context=action.app_context
                    )
                    logger.info(f"Click [{attempt}/{max_retries}] por selector")
                    element.click_input() # Use click_input consistently for UIA
                else:
                    logger.info(f"Click [{attempt}/{max_retries}] por coordenadas")
                    import pyautogui
                    x, y = action.position["x"], action.position["y"]
                    pyautogui.click(x, y)
                
                logger.info(f"Click exitoso")
                return True
                
            except Exception as e:
                logger.warning(f"Intento {attempt} fallido: {e}")
                
                # FALLBACK ROBUSTO: Si falla el selector, usar coordenadas inmediatamente
                # Esto salva la ejecución si el elemento cambió de ID o no se encuentra
                if action.position and action.selector:
                    logger.warning(f"⚠️ Fallback: Usando coordenadas ({action.position['x']}, {action.position['y']})")
                    try:
                        import pyautogui
                        x, y = action.position["x"], action.position["y"]
                        pyautogui.click(x, y)
                        return True
                    except Exception as ex:
                        logger.error(f"Fallback coordenadas también falló: {ex}")

                    if attempt < max_retries:
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"Click final fallido")
                        return False
    
    def _execute_double_click(self, action: Action) -> bool:
        """Doble Click con fallback."""
        max_retries = self.config.get("click_retries", 2)
        retry_delay = self.config.get("retry_delay", 1.0)
        
        for attempt in range(1, max_retries + 1):
            try:
                if action.selector:
                    element = self.selector_helper.find_element(
                        action.selector,
                        timeout=self.config.get("element_timeout", 2.0),
                        app_context=action.app_context
                    )
                    logger.info(f"Double Click [{attempt}/{max_retries}] por selector")
                    element.double_click_input() # pywinauto double click
                else:
                    logger.info(f"Double Click [{attempt}/{max_retries}] por coordenadas")
                    import pyautogui
                    x, y = action.position["x"], action.position["y"]
                    pyautogui.doubleClick(x, y)
                
                logger.info(f"Double Click exitoso")
                return True
                
            except Exception as e:
                logger.warning(f"Intento {attempt} fallido: {e}")
                
                if action.position and action.selector:
                    logger.warning(f"⚠️ Fallback: Usando coordenadas ({action.position['x']}, {action.position['y']})")
                    try:
                        import pyautogui
                        x, y = action.position["x"], action.position["y"]
                        pyautogui.doubleClick(x, y)
                        return True
                    except Exception as ex:
                        logger.error(f"Fallback coordenadas también falló: {ex}")

                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Double Click final fallido")
                    return False
    
    def _execute_type_text(self, action: Action) -> bool:
        """Type con selector o foco."""
        max_retries = self.config.get("type_retries", 1)
        
        for attempt in range(1, max_retries + 1):
            try:
                if action.selector:
                    element = self.selector_helper.find_element(
                        action.selector,
                        timeout=self.config.get("element_timeout", 5.0),
                        app_context=action.app_context
                    )
                    logger.info(f"Type [{attempt}/{max_retries}] en selector")
                    element.type_keys(action.text, with_spaces=True)
                else:
                    logger.info(f"Type [{attempt}/{max_retries}] en foco")
                    import pyautogui
                    pyautogui.typewrite(action.text, interval=0.05)
                
                logger.info(f"Texto escrito: {action.text[:50]}...")
                return True
                
            except Exception as e:
                logger.warning(f"Intento {attempt} fallido: {e}")
                if attempt == max_retries:
                    logger.error(f"Type final fallido")
                    return False
    
    def _execute_key_press(self, action: Action) -> bool:
        """Presionar tecla."""
        try:
            logger.info(f"Presionando: {action.key_code}")
            import pyautogui
            pyautogui.press(action.key_code.lower())
            logger.info(f"Tecla {action.key_code} presionada")
            return True
        except Exception as e:
            logger.error(f"Error: {e}")
            return False
    
    def _execute_key_combination(self, action: Action) -> bool:
        """Ejecuta combinación de teclas."""
        try:
            combination = action.combination
            logger.info(f"Ejecutando combinación: {combination}")
            
            # Parsear la combinación
            parts = combination.split("+")
            
            # Mapeo de teclas
            key_map = {
                "CTRL": "ctrl",
                "SHIFT": "shift",
                "ALT": "alt",
                "WIN": "win",
                "CMD": "command"
            }
            
            # Convertir a formato pyautogui
            keys = []
            for part in parts:
                if part in key_map:
                    keys.append(key_map[part])
                else:
                    keys.append(part.lower())
            
            # Caso especial: Ctrl+V con contenido del portapapeles
            if combination == "CTRL+V" and action.clipboard_content:
                logger.info(f"Pegando contenido del portapapeles: {action.clipboard_content[:50]}...")
                # Primero establecer el contenido del portapapeles
                self._set_clipboard_content(action.clipboard_content)
                time.sleep(0.1)
            
            # Ejecutar combinación
            import pyautogui
            pyautogui.hotkey(*keys)
            
            logger.info(f"Combinación {combination} ejecutada")
            return True
            
        except Exception as e:
            logger.error(f"Error ejecutando combinación: {e}")
            return False
    
    def _set_clipboard_content(self, content: str):
        """Establece el contenido del portapapeles."""
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                # Usar CF_UNICODETEXT para evitar errores con acentos (como en 'Impresión')
                win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, content)
            finally:
                win32clipboard.CloseClipboard()
        except:
            # Fallback usando tkinter
            try:
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                root.clipboard_clear()
                root.clipboard_append(content)
                root.update()
                root.destroy()
            except Exception as e:
                logger.warning(f"No se pudo establecer el portapapeles: {e}")

    
    def _execute_wait(self, action: Action) -> bool:
        """Espera."""
        logger.info(f"Esperando: {action.validation_rule}")
        time.sleep(action.wait_before)
        return True
    
    def _execute_validate(self, action: Action) -> bool:
        """Validación."""
        logger.info(f"Validando: {action.validation_rule}")
        return True
