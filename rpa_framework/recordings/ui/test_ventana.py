import time
import sys
import logging
from pywinauto import Application, findwindows

# Configurar logging para ver qué pasa
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_enfoque_ventana():
    patterns = ["Carestream Radiology Client", "Carestream Vue PACS"]
    logger.info(f"Buscando ventanas que contengan: {patterns}")
    
    try:
        all_wins = findwindows.find_elements()
        logger.info(f"Total de ventanas detectadas: {len(all_wins)}")
        
        found = False
        for win in all_wins:
            # logger.info(f"Ventana encontrada: '{win.name}'") # Descomentar para ver TODAS las ventanas
            for pattern in patterns:
                if pattern in win.name:
                    logger.info(f"🎯 MATCH ENCONTRADO: '{win.name}' (Pattern: {pattern})")
                    try:
                        app = Application(backend='uia').connect(handle=win.handle)
                        window = app.window(handle=win.handle)
                        
                        logger.info("Intentando set_focus()...")
                        window.set_focus()
                        
                        logger.info("✅ Ventana enfocada exitosamente.")
                        found = True
                        break
                    except Exception as e:
                        logger.error(f"❌ Error al conectar/enfocar: {e}")
            if found: break
            
        if not found:
            logger.warning("❌ No se encontró ninguna ventana que coincida.")
            logger.info("--- LISTA DE TODAS LAS VENTANAS DISPONIBLES ---")
            for win in all_wins:
                if win.name.strip():
                    logger.info(f" - {win.name}")
            
    except Exception as e:
        logger.error(f"Error crítico: {e}")

if __name__ == "__main__":
    test_enfoque_ventana()
    time.sleep(3)
