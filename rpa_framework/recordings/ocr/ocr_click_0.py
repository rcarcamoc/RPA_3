# Auto-generated OCR Click Module
# Generated: 2026-01-02T11:24:08.192889

def execute_ocr_click_0():
    """
    Acción OCR: Click en texto 'búsqueda de pacientes'
    
    Busca el texto 'búsqueda de pacientes' en la pantalla
    y hace click en su ubicación.
    """
    import sys
    import os
    # Add framework root to path to allow importing 'ocr'
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

    from ocr.engine import OCREngine
    from ocr.matcher import OCRMatcher
    from ocr.actions import OCRActions
    
    
    # Database Tracking Support
    try:
        import mysql.connector
        def db_update_status(status='En Proceso'):
            try:
                conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
                cursor = conn.cursor()
                query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
                cursor.execute(query, ('ocr_click_0', status))
                conn.commit()
                conn.close()
            except: pass
    except ImportError:
        def db_update_status(status='En Proceso'): pass
    
    db_update_status('En Proceso')
    
    # Parámetros de ROI (10% izquierdo)
    import mss
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        roi_percent = 20 # Aumentar a 20% para asegurar visibilidad
        region = {
            "top": monitor["top"],
            "left": monitor["left"],
            "width": int(monitor["width"] * (roi_percent / 100)),
            "height": monitor["height"]
        }

    try:
        # Inicializar motor OCR (Tesseract)
        engine = OCREngine(
            engine='tesseract',
            language='spa', # Usar 'spa' directamente para Tesseract
            confidence_threshold=0.1, 
            use_gpu=False
        )
        
        # Inicializar matcher
        matcher = OCRMatcher(threshold=50) 
        
        # Inicializar acciones
        actions = OCRActions(engine, matcher, delay=0.3)
        
        # Ejecutar acción
        result = actions.click_on_text(
            search_term='búsqueda de pacientes',
            offset_x=0,
            offset_y=0,
            fuzzy=True,
            button='left',
            region=region
        )
        
        db_update_status('En Proceso')
        return result
    
    except Exception as e:
        db_update_status('error')
        return {
            'action': 'click',
            'status': 'error',
            'error': str(e),
            'text_searched': 'búsqueda de pacientes'
        }


# Alias para compatibilidad
ocr_click_0 = execute_ocr_click_0


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)
    print('Executing execute_ocr_click_0...')
    res = execute_ocr_click_0()
    print(f'Result: {res}')
