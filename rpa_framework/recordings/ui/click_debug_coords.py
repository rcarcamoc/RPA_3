import pyautogui
import time
import logging
import sys
from pathlib import Path

# Configurar Paths para importar utilidades
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.visual_feedback import VisualFeedback

# --- VARIABLES DE CONFIGURACIÓN ---
# Coordenadas base del primer click (Secundario)
SCREEN_X = 860
SCREEN_Y = 150

# Offsets para el segundo click (Izquierdo)
OFFSET_X = 50
OFFSET_Y = 180 # Ajustado según tu cambio reciente
# ----------------------------------

# Configurar logging básico
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def execute_clicks():
    vf = VisualFeedback()
    
    logger.info("Iniciando secuencia de clicks HUMANIZADOS.")
    logger.info("Esperando 2 segundos...")
    time.sleep(2)

    # 1. Click Secundario (Humanizado)
    logger.info(f"Ejecutando Click secundario en ({SCREEN_X}, {SCREEN_Y})")
    if vf: vf.highlight_click(SCREEN_X, SCREEN_Y)
    
    # Mover suavemente
    pyautogui.moveTo(SCREEN_X, SCREEN_Y, duration=0.5, tween=pyautogui.easeInOutQuad)
    time.sleep(0.1)
    
    # Click manual con pausa entre presionar y soltar
    pyautogui.mouseDown(button='right')
    time.sleep(0.15)
    pyautogui.mouseUp(button='right')
    
    # Espera más larga para que el menú contextual aparezca
    time.sleep(1.2)

    # 2. Click Izquierdo (con offset, Humanizado)
    new_x = SCREEN_X + OFFSET_X
    new_y = SCREEN_Y + OFFSET_Y
    
    logger.info(f"Ejecutando Click izquierdo en ({new_x}, {new_y}) [Offset: {OFFSET_X}, {OFFSET_Y}]")
    if vf: vf.highlight_click(new_x, new_y)
    
    # Mover suavemente al segundo punto
    pyautogui.moveTo(new_x, new_y, duration=0.4, tween=pyautogui.easeOutQuad)
    time.sleep(0.1)
    
    # Click manual
    pyautogui.mouseDown(button='left')
    time.sleep(0.1)
    pyautogui.mouseUp(button='left')

    logger.info("Secuencia completada.")

if __name__ == "__main__":
    execute_clicks()
