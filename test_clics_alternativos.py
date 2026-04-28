import sys
import time
import logging
from pathlib import Path
from datetime import datetime
import pyautogui

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent / "rpa_framework"))
sys.path.insert(0, str(Path(__file__).parent))

from pywinauto import Application, findwindows
from rpa_framework.core.executor import ActionExecutor
from rpa_framework.core.action import Action, ActionType

try:
    from rpa_framework.utils.visual_feedback import VisualFeedback
    vf = VisualFeedback()
except ImportError:
    vf = None

# Configurar logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestCliceAlternativos:
    def __init__(self):
        self.app = None
        self.executor = None

    def setup_ris(self):
        logger.info("Conectando a Carestream RIS...")
        titulos = findwindows.find_elements(title_re=".*Carestream RIS V11.*", backend='uia')
        if titulos:
            self.app = Application(backend='uia').connect(handle=titulos[0].handle)
            self.main_window = self.app.window(title_re=".*Carestream RIS V11.*")
            self.main_window.set_focus()
            self.executor = ActionExecutor(self.app, {})
            return True
        return False

    def run(self):
        if not self.setup_ris():
            logger.error("No se encontró Carestream RIS")
            return

        x, y = 295, 123
        auto_id = 'cbxClResultadocritico1'

        # --- ALTERNATIVA 1: Click Input Robusto (UIA) ---
        if vf: vf.show_message("Intentando Alt 1: Pywinauto Click Input", duration=2)
        logger.info("Alternativa 1: Click nativo...")
        try:
            element = self.main_window.child_window(auto_id=auto_id, control_type="ComboBox")
            element.click_input()
            if vf: vf.show_message("Alt 1 completada", duration=1)
        except Exception as e:
            logger.error(f"Alt 1 falló: {e}")

        time.sleep(3)

        # --- ALTERNATIVA 2: Clic Sostenido Manual (PyAutoGUI) ---
        if vf: vf.show_message("Intentando Alt 2: PyAutoGUI Hold (Coords)", duration=2)
        logger.info("Alternativa 2: PyAutoGUI sostenido...")
        try:
            pyautogui.moveTo(x, y, duration=0.6)
            pyautogui.mouseDown(x, y)
            time.sleep(0.8) 
            pyautogui.mouseUp(x, y)
            if vf: vf.show_message("Alt 2 completada", duration=1)
        except Exception as e:
            logger.error(f"Alt 2 falló: {e}")

        time.sleep(3)


if __name__ == "__main__":
    test = TestCliceAlternativos()
    test.run()
