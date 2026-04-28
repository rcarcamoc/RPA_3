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
        from fuzzywuzzy import fuzz
        
        # Buscar texto para clic robusto con reintentos evaluando ORACIONES
        delays = [3, 3, 3, 3, 3]
        search_terms = ['Búsqueda de Pacientes', 'Patient Search']
        matches = None
        region = {'left': 0, 'top': 0, 'width': 182, 'height': 1010}
        
        for attempt, delay in enumerate(delays):
            if delay > 0:
                print(f"Intento {attempt + 1}: Reintentando en {delay} segundos...")
                time.sleep(delay)
            
            # 1. Capturar pantalla localmente
            actions.capture_screenshot(region=region)
            
            # 2. Extraer texto crudo con ubicaciones
            ocr_results = engine.extract_text_with_location(actions.last_screenshot)
            
            # Ajustar coordenadas globales
            for res in ocr_results:
                res['center']['x'] += region['left']
                res['center']['y'] += region['top']
                
            # 3. Evaluar oraciones (Agrupando bloques en la misma línea Y)
            highest_score = 0
            best_res = None
            
            # Ordenar de arriba a abajo, izquierda a derecha (tolerancia de 15px en Y para "misma línea")
            ocr_results.sort(key=lambda x: (int(x['center']['y'] / 15), x['center']['x']))
            
            for term in search_terms:
                term_lower = term.lower()
                
                # Probar cada bloque individual y combinaciones de hasta 3 palabras consecutivas
                for window_size in [1, 2, 3]:
                    if len(ocr_results) < window_size:
                        continue
                        
                    for i in range(len(ocr_results) - window_size + 1):
                        window = ocr_results[i:i+window_size]
                        
                        # Si combinamos varios bloques, deben estar casi en la misma altura Y
                        if window_size > 1:
                            y_diff = abs(window[0]['center']['y'] - window[-1]['center']['y'])
                            if y_diff > 25: 
                                continue # Saltar si están en líneas distintas
                                
                        texto_combinado = " ".join([w['text'] for w in window])
                        
                        # Usar fuzz.ratio estricto (compara longitud total de la oración, evita falsos positivos con palabras cortas como "de")
                        score = fuzz.ratio(term_lower, texto_combinado.lower())
                        
                        if score > highest_score:
                            highest_score = score
                            best_res = window[0].copy()
                            best_res['text'] = texto_combinado
                            best_res['match_term'] = term
                            
            if highest_score >= 75: # Umbral del 75% sobre la oración completa
                matches = [best_res]
                print(f"  ✅ Encontrado: '{best_res['text']}' (Similitud Oración: {highest_score}% con '{best_res['match_term']}')")
                break
            else:
                if best_res:
                    print(f"  ⏳ Mejor intento OCR: '{best_res['text']}' (Similitud: {highest_score}% - Se requiere >= 75%)")
        
        # Si falla tras los reintentos automáticos, hacemos un intento final sin intervención
        if not matches:

            actions.capture_screenshot(region=region)
            ocr_results = engine.extract_text_with_location(actions.last_screenshot)
            for res in ocr_results:
                res['center']['x'] += region['left']
                res['center']['y'] += region['top']
            
            ocr_results.sort(key=lambda x: (int(x['center']['y'] / 15), x['center']['x']))
            highest_score = 0
            best_res = None
            
            for term in search_terms:
                term_lower = term.lower()
                for window_size in [1, 2, 3]:
                    if len(ocr_results) < window_size: continue
                    for i in range(len(ocr_results) - window_size + 1):
                        window = ocr_results[i:i+window_size]
                        if window_size > 1 and abs(window[0]['center']['y'] - window[-1]['center']['y']) > 25: continue
                        texto_combinado = " ".join([w['text'] for w in window])
                        score = fuzz.ratio(term_lower, texto_combinado.lower())
                        if score > highest_score:
                            highest_score = score
                            best_res = window[0].copy()
                            best_res['text'] = texto_combinado
            
            if highest_score >= 75:
                matches = [best_res]

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
                'message': f'No se encontró ninguno de los términos {search_terms} tras reintentos'
            }

        
        # Verificar si se encontró y cliqueó con éxito
        if not result or result.get('status') != 'success':
            error_obs = 'No se encontró el botón "Búsqueda" o "Patient Search" en el menú lateral'
            try:
                try:
                    from utils.error_handler import handle_error_and_exit
                except ImportError:
                    from rpa_framework.utils.error_handler import handle_error_and_exit
                handle_error_and_exit("busca_busqueda de pacientes", error_obs)
            except ImportError:
                print(f"ERROR: {error_obs}")
                sys.exit(1)
            
        return result
    
    except SystemExit:
        sys.exit(1)
    except Exception as e:
        error_msg = f'Excepción crítica: {str(e)}'
        try:
            try:
                from utils.error_handler import handle_error_and_exit
            except ImportError:
                from rpa_framework.utils.error_handler import handle_error_and_exit
            handle_error_and_exit("busca_busqueda de pacientes", error_msg)
        except ImportError:
            print(error_msg)
            sys.exit(1)


# Alias para compatibilidad
ocr_click_0 = execute_ocr_click_0


if __name__ == '__main__':
    print('🚀 Executing execute_ocr_click_0...')
    res = execute_ocr_click_0()
    print(f'Result: {res}')
