# rpa_framework/ocr/code_generator.py
"""
Generador de código Python para acciones OCR.
Refactorizado de forma modular junto con rpa_framework/ocr/code_templates_mixin.py.
"""

from typing import Dict, Optional
from datetime import datetime
import logging

from .code_templates_mixin import OCRCodeTemplatesMixin

logger = logging.getLogger(__name__)


class OCRCodeGenerator(OCRCodeTemplatesMixin):
    """
    Generador de código Python para acciones OCR.
    
    Produce módulos ejecutables para cada acción registrada.
    """
    
    def __init__(self, engine: str = 'easyocr', language: str = 'es'):
        """
        Inicializar generador.
        
        Args:
            engine: Motor OCR a usar
            language: Idioma para OCR
        """
        self.engine = engine
        self.language = language
        self.generated_count = 0
        
        logger.info(f"OCRCodeGenerator inicializado (engine: {engine})")
        
    def _get_db_tracking_code(self, node_name: str) -> str:
        """Retorna el fragmento de código para tracking de BD."""
        return f'''
    # Database Tracking Support
    try:
        import mysql.connector
        def db_update_status(status='En Proceso'):
            try:
                conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
                cursor = conn.cursor()
                query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
                cursor.execute(query, ('{node_name}', status))
                conn.commit()
                conn.close()
            except: pass
    except ImportError:
        def db_update_status(status='En Proceso'): pass
    
    db_update_status('En Proceso')
'''
    
    def generate_click_module(
        self,
        text_to_find: str,
        offset_x: int = 0,
        offset_y: int = 0,
        fuzzy: bool = True,
        button: str = 'left',
        module_name: Optional[str] = None
    ) -> Dict:
        """
        Generar módulo para click basado en OCR.
        
        Args:
            text_to_find: Texto a buscar
            offset_x: Desplazamiento X
            offset_y: Desplazamiento Y
            fuzzy: Usar búsqueda fuzzy
            button: Botón del mouse
            module_name: Nombre personalizado del módulo
        
        Returns:
            Dict con {name, code, function_name}
        """
        if not module_name:
            module_name = f"ocr_click_{self.generated_count}"
            self.generated_count += 1
        
        function_name = f"execute_{module_name}".replace('-', '_')
        
        code = f'''# Auto-generated OCR Click Module
# Generated: {datetime.now().isoformat()}

def {function_name}():
    """
    Acción OCR: Click en texto '{text_to_find}'
    
    Busca el texto '{text_to_find}' en la pantalla
    y hace click en su ubicación.
    """
    import sys
    import os
    # Add framework root to path to allow importing 'ocr'
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

    from ocr.engine import OCREngine
    from ocr.matcher import OCRMatcher
    from ocr.actions import OCRActions
    
    {self._get_db_tracking_code(module_name)}
    try:
        # Inicializar motor OCR
        engine = OCREngine(
            engine='{self.engine}',
            language='{self.language}',
            confidence_threshold=0.5,
            use_gpu=True
        )
        
        # Inicializar matcher
        matcher = OCRMatcher(threshold=80)
        
        # Inicializar acciones
        actions = OCRActions(engine, matcher, delay=0.3)
        
        # Ejecutar acción
        result = actions.click_on_text(
            search_term='{text_to_find}',
            offset_x={offset_x},
            offset_y={offset_y},
            fuzzy={str(fuzzy)},
            button='{button}'
        )
        
        db_update_status('En Proceso')
        return result
    
    except Exception as e:
        db_update_status('error')
        return {{
            'action': 'click',
            'status': 'error',
            'error': str(e),
            'text_searched': '{text_to_find}'
        }}


# Alias para compatibilidad
{module_name} = {function_name}
'''
        
        return {
            'name': module_name,
            'function_name': function_name,
            'code': code,
            'action_type': 'click',
            'parameters': {
                'text_to_find': text_to_find,
                'offset_x': offset_x,
                'offset_y': offset_y,
                'fuzzy': fuzzy,
                'button': button
            }
        }
    
    def validate_code(self, code: str) -> bool:
        """
        Validar sintaxis del código generado.
        
        Returns:
            True si es válido, False si no
        """
        try:
            compile(code, '<string>', 'exec')
            logger.info("Código validado exitosamente")
            return True
        except SyntaxError as e:
            logger.error(f"Error de sintaxis en código generado: {e}")
            return False


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    gen = OCRCodeGenerator(engine='easyocr', language='es')
    module = gen.generate_click_module(
        text_to_find='Enviar',
        offset_x=0,
        offset_y=0,
        fuzzy=True
    )
    print(f"Módulo: {module['name']}")
    print(f"Función: {module['function_name']}")
    print(f"Código válido: {gen.validate_code(module['code'])}")
    print("---")
    print(module['code'])
