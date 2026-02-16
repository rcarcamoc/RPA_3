# Auto-generated OCR Click Module
# Generated: 2026-02-04T08:28:03.202592

def execute_ocr_click_0():
    """
    Acción OCR: Click en texto 'estado'
    
    Busca el texto 'estado' en la pantalla
    y hace click en su ubicación.
    """
    import sys
    import time
    import os
    # Add framework root to path to allow importing 'ocr'
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

    from ocr.engine import OCREngine
    from ocr.matcher import OCRMatcher
    from ocr.actions import OCRActions
    
    # Identificación del Registro via variable de entorno
    id_registro = os.environ.get('VAR_id_registro')
    
    # Database Tracking Support
    import mysql.connector
    def db_update(status='En Proceso', obs=None, node='busca_busqueda de pacientes'):
        if not id_registro:
            return
        try:
            conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
            cursor = conn.cursor()
            
            if status == 'Error':
                query = "UPDATE registro_acciones SET estado = 'Error', observacion = %s, `update` = NOW() WHERE id = %s"
                cursor.execute(query, (obs, id_registro))
            else:
                query = "UPDATE registro_acciones SET estado = %s, ultimo_nodo = %s, `update` = NOW() WHERE id = %s"
                cursor.execute(query, (status, node, id_registro))
                
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error DB: {e}")

    # Update inicial: Indicar inicio de este nodo
    db_update(status='En Proceso')

    try:
        # Inicializar motor OCR
        engine = OCREngine(
            engine='tesseract',
            confidence_threshold=0.5
        )
        
        # Inicializar matcher
        matcher = OCRMatcher(threshold=80)
        
        # Inicializar acciones
        actions = OCRActions(engine, matcher, delay=0.3)
        
        # Buscar texto para clic robusto
        matches = actions.capture_and_find(
            search_term='búsqueda',
            fuzzy=True,
            region={'left': 0, 'top': 0, 'width': 182, 'height': 1010}
        )
        
        if matches:
            best = matches[0]
            click_x = int(best['center']['x'])
            click_y = int(best['center']['y'])
            
            # Highlight visual
            try:
                from rpa_framework.utils.visual_feedback import VisualFeedback
                vf = VisualFeedback()
                vf.highlight_click(click_x, click_y)
            except: pass
            
            # Simular clic robusto (mouseDown + wait + mouseUp)
            import pyautogui
            pyautogui.moveTo(click_x, click_y, duration=0.2)
            time.sleep(0.5) # Pausa solicitada sobre la coordenada
            pyautogui.mouseDown(click_x, click_y, button='left')
            time.sleep(0.15)
            pyautogui.mouseUp(click_x, click_y, button='left')
            time.sleep(0.3)
            
            result = {
                'action': 'click',
                'status': 'success',
                'text_found': best['text'],
                'position': {'x': click_x, 'y': click_y}
            }
        else:
            result = {'status': 'error', 'error': 'No se encontró el texto'}
        
        # Verificar si se encontró y cliqueó con éxito
        if not result or result.get('status') != 'success':
            db_update(status='Error', obs='error en busqueda de pacientes')
            print("ERROR: no encontro busqueda de pacientes")
            sys.exit(1)
            
        return result
    
    except SystemExit:
        # Re-lanzar sys.exit para que el proceso termine
        sys.exit(1)
    except Exception as e:
        print(f"Excepción crítica: {e}")
        db_update(status='Error', obs=f'Excepción: {str(e)}')
        print("ERROR: no encontro busqueda de pacientes")
        sys.exit(1)


# Alias para compatibilidad
ocr_click_0 = execute_ocr_click_0


if __name__ == '__main__':
    print('🚀 Executing execute_ocr_click_0...')
    res = execute_ocr_click_0()
    print(f'Result: {res}')
