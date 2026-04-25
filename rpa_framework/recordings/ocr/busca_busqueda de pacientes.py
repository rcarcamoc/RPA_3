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
    
    # Delay inicial de 2 segundos solicitado
    time.sleep(2)
    
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
        
        # Buscar texto para clic robusto con reintentos
        delays = [5, 3, 5]
        matches = None
        
        for attempt, delay in enumerate(delays):
            if delay > 0:
                print(f"Intento {attempt + 1}: Reintentando en {delay} segundos...")
                time.sleep(delay)
            
            matches = actions.capture_and_find(
                search_term='búsqueda',
                fuzzy=True,
                region={'left': 0, 'top': 0, 'width': 182, 'height': 1010}
            )
            if matches:
                break
        
        # Si falla tras los reintentos automáticos, solicitar intervención del usuario
        if not matches:
            import pyautogui
            pyautogui.alert(
                text='No se encontró el botón "búsqueda" después de varios intentos.\n\nPor favor, asegúrese de que el menú lateral del RIS esté visible y presione OK para reintentar.',
                title='RPA - Intervención Requerida'
            )
            # Intento final tras la intervención
            matches = actions.capture_and_find(
                search_term='búsqueda',
                fuzzy=True,
                region={'left': 0, 'top': 0, 'width': 182, 'height': 1010}
            )

        result = None
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
            # Si aún no se encuentra, se marcará como error
            result = {
                'action': 'click',
                'status': 'error',
                'message': 'No se encontró el texto "búsqueda" tras reintentos e intervención manual'
            }

        
        # Verificar si se encontró y cliqueó con éxito
        if not result or result.get('status') != 'success':
            error_obs = 'No se encontró el texto "búsqueda" en el menú lateral'
            db_update(status='Error', obs=error_obs)
            
            # Notificación Visual y Telegram
            try:
                from utils.telegram_manager import enviar_alerta_todos
                from rpa_framework.utils.visual_feedback import VisualFeedback
                
                vf = VisualFeedback()
                vf.show_persistent_message(f"❌ ERROR: {error_obs}", "error_ocr", bg_color="#F44336", fg_color="#FFFFFF")
                
                msg_telegram = f"❌ <b>Error OCR: busca_busqueda de pacientes</b>\n{error_obs}\nPor favor, verifique que el menú del RIS esté visible."
                enviar_alerta_todos(msg_telegram)
            except Exception as tel_err:
                print(f"Error al enviar notificaciones: {tel_err}")

            print(f"ERROR: {error_obs}")
            sys.exit(1)
            
        return result
    
    except SystemExit:
        sys.exit(1)
    except Exception as e:
        error_msg = f'Excepción crítica: {str(e)}'
        print(error_msg)
        db_update(status='Error', obs=error_msg)
        
        # Notificación en caso de excepción
        try:
            from utils.telegram_manager import enviar_alerta_todos
            enviar_alerta_todos(f"❌ <b>Error Crítico: busca_busqueda de pacientes</b>\n{error_msg}")
        except: pass
        
        sys.exit(1)


# Alias para compatibilidad
ocr_click_0 = execute_ocr_click_0


if __name__ == '__main__':
    print('🚀 Executing execute_ocr_click_0...')
    res = execute_ocr_click_0()
    print(f'Result: {res}')
