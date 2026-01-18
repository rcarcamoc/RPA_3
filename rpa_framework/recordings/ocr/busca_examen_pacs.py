# Auto-generated OCR Click Module
# Generated: 2026-01-02T11:57:00
# Adapted for project structure

def execute_busca_examen_pacs():
    """
    Acción OCR: Click secundario en línea de examen+fecha

    1) Lee examen y fecha desde MySQL:
       SELECT SUBSTRING_INDEX(diagnostico, '\n', 1) AS examen, date(fecha_agendada) as fecha
       FROM ris.registro_acciones
       WHERE estado = 'En Proceso';

    2) Toma screenshot.
    3) Busca en OCR la línea donde coincidan examen y fecha (dd-mm-yyyy).
    4) Hace clic secundario en el punto "triangular" calculado.
    """
    import sys
    import os
    from datetime import datetime
    import logging

    # Add framework root to path to allow importing 'ocr'
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

    from ocr.engine import OCREngine
    from ocr.matcher import OCRMatcher
    from ocr.actions import OCRActions

    import pyautogui
    
    # Configuración de logging local
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # ---------- Métodos de tracking en BD ----------
    try:
        import mysql.connector
        def db_update_status(status='En Proceso'):
            try:
                conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
                cursor = conn.cursor()
                query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
                cursor.execute(query, ('busca_examen_pacs', status))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"Error actualizando estado en BD: {e}")
                pass
    except ImportError:
        def db_update_status(status='En Proceso'):
            pass
    # ----------------------------------------------------------------------

    db_update_status('En Proceso')

    # ---------- 1. Leer examen y fecha desde MySQL ----------
    examen_text = None
    fecha_text = None
    
    try:
        conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
        cursor = conn.cursor()
        query = """
            SELECT 
                SUBSTRING_INDEX(diagnostico, '\\n', 1) AS examen, 
                DATE(fecha_agendada) AS fecha
            FROM ris.registro_acciones
            WHERE estado = 'En Proceso'
            LIMIT 1
        """
        cursor.execute(query)
        row = cursor.fetchone()
        conn.close()

        if not row:
            logger.warning("No se encontraron registros 'En Proceso' en la BD")
            db_update_status('sin_datos')
            return {
                'action': 'click_examen_fecha',
                'status': 'no_data',
                'error': 'No hay registros con estado En Proceso'
            }

        examen_db, fecha_db = row  # fecha_db es datetime.date
        examen_text = str(examen_db).strip()
        # Formato de pantalla dd-mm-yyyy si fecha_db es objeto date
        if hasattr(fecha_db, 'strftime'):
            fecha_text = fecha_db.strftime('%d-%m-%Y')
        else:
             # Fallback si viene como string
            fecha_text = str(fecha_db)
            
        logger.info(f"Buscando Examen: '{examen_text}', Fecha: '{fecha_text}'")

    except Exception as e:
        logger.error(f"Error consultando BD: {e}")
        db_update_status('error')
        return {
            'action': 'click_examen_fecha',
            'status': 'error_db',
            'error': str(e)
        }

    try:
        # ---------- 2. Inicializar motor OCR ----------
        engine = OCREngine(
            engine='easyocr',
            language='es',
            confidence_threshold=0.5,
            use_gpu=True
        )

        matcher = OCRMatcher(threshold=80)
        # No necesitamos actions para la lógica custom, pero lo inicializamos si se requiere
        # actions = OCRActions(engine, matcher, delay=0.3) 

        # ---------- 3. Tomar screenshot de toda la pantalla ----------
        screenshot_path = os.path.join(os.path.dirname(__file__), 'tmp_examen_fecha.png')
        img = pyautogui.screenshot()
        img.save(screenshot_path)
        logger.info(f"Screenshot guardado en: {screenshot_path}")

        # ---------- 4. Ejecutar OCR sobre el screenshot ----------
        # OCREngine.extract_text_with_location retorna lista de dicts con:
        # 'text', 'confidence', 'bbox', 'center': {'x', 'y'}, ...
        ocr_results = engine.extract_text_with_location(screenshot_path)
        logger.info(f"OCR encontró {len(ocr_results)} elementos de texto")

        # ---------- 5. Agrupar por línea y buscar examen + fecha ----------
        # Criterio: coordenada Y del centro. Agrupamos por filas de ~20px de altura
        candidate_click_pos = None
        line_map = {}

        for box in ocr_results:
            center_y = box['center']['y']
            # Agrupar usando una tolerancia. 
            # Dividir por 20 (altura aprox de linea) y usar entero como ID de linea
            line_id = int(center_y / 20)
            line_map.setdefault(line_id, []).append(box)

        # Normalizar texto para comparar
        examen_lower = examen_text.lower()
        fecha_lower = fecha_text.lower()
        
        found_data = False

        for line_id, boxes in line_map.items():
            # Construir texto completo de la línea para búsqueda rápida
            # Ordenamos por X para que el texto tenga sentido
            boxes.sort(key=lambda b: b['center']['x'])
            full_line_text = ' '.join([b['text'] for b in boxes]).strip()
            full_line_lower = full_line_text.lower()

            # Verificación laxa: buscar las palabras clave
            if examen_lower in full_line_lower and fecha_lower in full_line_lower:
                logger.info(f"Línea candidata encontrada (ID {line_id}): {full_line_text}")
                
                # Buscamos los boxes específicos que contienen las partes
                exam_boxes = [b for b in boxes if examen_lower in b['text'].lower() or b['text'].lower() in examen_lower]
                
                # Para la fecha, buscamos coincidencia exacta o parcial fuerte
                date_boxes = [b for b in boxes if fecha_lower in b['text'].lower()]

                # Si no encontramos boxes exactos (porque el OCR partió las palabras), 
                # usamos la lógica de linea general, pero necesitamos coordenadas para triangular.
                # Intentamos coger el primer box de la linea y el ultimo como fallback si no hay match especifico,
                # pero mejor intentamos filtrar de nuevo.
                
                if not exam_boxes: 
                    # Aproximacion: tomar los boxes de la izquierda que podrian ser el examen
                    exam_boxes = boxes[:len(boxes)//2]
                if not date_boxes:
                    # Aproximacion: tomar los boxes de la derecha (fecha suele estar al final/derecha)
                    date_boxes = boxes[len(boxes)//2:]

                if exam_boxes and date_boxes:
                    eb = exam_boxes[0]
                    dbx = date_boxes[0]

                    exam_cy = eb['center']['y']
                    date_cy = dbx['center']['y']
                    
                    # Validación estricta de alineación vertical (mismo eje Y)
                    if abs(exam_cy - date_cy) > 15: # Tolerancia 15px
                        logger.warning(f"Coincidencia encontrada pero desalineada (Diff Y: {abs(exam_cy - date_cy)}px). Se omite candidato.")
                        # Si es crítico, se podría setear flag de error, pero 'continue' buscará otra línea válida
                        continue

                    # Punto "triangular": punto medio entre centro de examen y centro de fecha
                    exam_cx = eb['center']['x']
                    date_cx = dbx['center']['x']
                    
                    click_x = int((exam_cx + date_cx) / 2)
                    click_y = int((exam_cy + date_cy) / 2)

                    candidate_click_pos = (click_x, click_y)
                    found_data = True
                    break
        
        if not candidate_click_pos:
            logger.warning(f"No se encontró coincidencia para Examen: {examen_text} y Fecha: {fecha_text}")
            db_update_status('no_match')
            return {
                'action': 'click_examen_fecha',
                'status': 'no_match',
                'examen': examen_text,
                'fecha': fecha_text
            }

        # ---------- 6. Hacer clic secundario en la posición calculada ----------
        logger.info(f"Haciendo click secundario en: {candidate_click_pos}")
        pyautogui.click(candidate_click_pos[0], candidate_click_pos[1], button='right')

        db_update_status('En Proceso')
        return {
            'action': 'click_examen_fecha',
            'status': 'ok',
            'click_position': candidate_click_pos,
            'examen': examen_text,
            'fecha': fecha_text
        }

    except Exception as e:
        logger.error(f"Error durante ejecución: {e}")
        db_update_status('error')
        return {
            'action': 'click_examen_fecha',
            'status': 'error',
            'error': str(e),
            'examen': examen_text,
            'fecha': fecha_text
        }


# Alias para compatibilidad
busca_examen_pacs = execute_busca_examen_pacs


if __name__ == '__main__':
    print('🚀 Executing execute_busca_examen_pacs...')
    res = execute_busca_examen_pacs()
    print(f'Result: {res}')
