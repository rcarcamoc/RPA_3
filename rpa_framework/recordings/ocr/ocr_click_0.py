# Auto-generated OCR Click Module
# Generated: 2026-02-04T08:28:03.202592

def execute_ocr_click_0():
    """
    Acción OCR: Click en texto 'estado'
    
    Busca el texto 'estado' en la pantalla
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

    try:
        # Inicializar motor OCR
        engine = OCREngine(
            engine='tesseract',
            language='es',
            confidence_threshold=0.5,
            use_gpu=True
        )
        
        # Inicializar matcher
        matcher = OCRMatcher(threshold=80)
        
        # Inicializar acciones
        actions = OCRActions(engine, matcher, delay=0.3)
        
        # Ejecutar acción
        result = actions.click_on_text(
            search_term='estado',
            offset_x=0,
            offset_y=0,
            fuzzy=True,
            button='left'
        )
        
        db_update_status('En Proceso')
        return result
    
    except Exception as e:
        db_update_status('error')
        return {
            'action': 'click',
            'status': 'error',
            'error': str(e),
            'text_searched': 'estado'
        }


# Alias para compatibilidad
ocr_click_0 = execute_ocr_click_0


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)
    print('🚀 Executing execute_ocr_click_0...')
    res = execute_ocr_click_0()
    print(f'Result: {res}')
