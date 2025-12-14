# rpa_framework/ocr/code_generator.py

import json
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class OCRCodeGenerator:
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
    from rpa_framework.ocr.engine import OCREngine
    from rpa_framework.ocr.matcher import OCRMatcher
    from rpa_framework.ocr.actions import OCRActions
    
    try:
        # Inicializar motor OCR
        engine = OCREngine(
            engine='{self.engine}',
            language='{self.language}',
            confidence_threshold=0.5,
            use_gpu=False
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
            fuzzy={str(fuzzy).lower()},
            button='{button}'
        )
        
        return result
    
    except Exception as e:
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
    
    def generate_copy_module(
        self,
        text_to_find: str,
        fuzzy: bool = True,
        case_sensitive: bool = False,
        module_name: Optional[str] = None
    ) -> Dict:
        """Generar módulo para buscar y copiar texto."""
        if not module_name:
            module_name = f"ocr_copy_{self.generated_count}"
            self.generated_count += 1
        
        function_name = f"execute_{module_name}".replace('-', '_')
        
        code = f'''# Auto-generated OCR Copy Module
# Generated: {datetime.now().isoformat()}

def {function_name}():
    """
    Acción OCR: Copiar texto '{text_to_find}'
    
    Busca el texto '{text_to_find}' en la pantalla,
    lo selecciona y lo copia al portapapeles.
    """
    from rpa_framework.ocr.engine import OCREngine
    from rpa_framework.ocr.matcher import OCRMatcher
    from rpa_framework.ocr.actions import OCRActions
    
    try:
        # Inicializar motor OCR
        engine = OCREngine(
            engine='{self.engine}',
            language='{self.language}',
            confidence_threshold=0.5,
            use_gpu=False
        )
        
        # Inicializar matcher
        matcher = OCRMatcher(threshold=80)
        
        # Inicializar acciones
        actions = OCRActions(engine, matcher, delay=0.3)
        
        # Ejecutar acción
        result = actions.copy_text_by_ocr(
            search_term='{text_to_find}',
            fuzzy={str(fuzzy).lower()},
            case_sensitive={str(case_sensitive).lower()}
        )
        
        return result
    
    except Exception as e:
        return {{
            'action': 'copy',
            'status': 'error',
            'error': str(e),
            'text_searched': '{text_to_find}'
        }}


# Alias
{module_name} = {function_name}
'''
        
        return {
            'name': module_name,
            'function_name': function_name,
            'code': code,
            'action_type': 'copy',
            'parameters': {
                'text_to_find': text_to_find,
                'fuzzy': fuzzy,
                'case_sensitive': case_sensitive
            }
        }
    
    def generate_select_module(
        self,
        text_to_find: str,
        fuzzy: bool = True,
        module_name: Optional[str] = None
    ) -> Dict:
        """Generar módulo para seleccionar texto."""
        if not module_name:
            module_name = f"ocr_select_{self.generated_count}"
            self.generated_count += 1
        
        function_name = f"execute_{module_name}".replace('-', '_')
        
        code = f'''# Auto-generated OCR Select Module
# Generated: {datetime.now().isoformat()}

def {function_name}():
    """
    Acción OCR: Seleccionar texto '{text_to_find}'
    
    Busca el texto '{text_to_find}' en la pantalla
    y lo selecciona (triple-click).
    """
    from rpa_framework.ocr.engine import OCREngine
    from rpa_framework.ocr.matcher import OCRMatcher
    from rpa_framework.ocr.actions import OCRActions
    
    try:
        engine = OCREngine(
            engine='{self.engine}',
            language='{self.language}',
            confidence_threshold=0.5,
            use_gpu=False
        )
        matcher = OCRMatcher(threshold=80)
        actions = OCRActions(engine, matcher, delay=0.3)
        
        result = actions.select_text(
            search_term='{text_to_find}',
            fuzzy={str(fuzzy).lower()}
        )
        
        return result
    
    except Exception as e:
        return {{
            'action': 'select',
            'status': 'error',
            'error': str(e),
            'text_searched': '{text_to_find}'
        }}


{module_name} = {function_name}
'''
        
        return {
            'name': module_name,
            'function_name': function_name,
            'code': code,
            'action_type': 'select',
            'parameters': {
                'text_to_find': text_to_find,
                'fuzzy': fuzzy
            }
        }
    
    def generate_type_near_text_module(
        self,
        reference_text: str,
        text_to_type: str,
        offset_x: int = 50,
        offset_y: int = 0,
        fuzzy: bool = True,
        module_name: Optional[str] = None
    ) -> Dict:
        """Generar módulo para escribir cerca de un elemento."""
        if not module_name:
            module_name = f"ocr_type_{self.generated_count}"
            self.generated_count += 1
        
        function_name = f"execute_{module_name}".replace('-', '_')
        
        # Escapar comillas en el texto
        text_escaped = text_to_type.replace("'", "\\'")
        
        code = f'''# Auto-generated OCR Type Module
# Generated: {datetime.now().isoformat()}

def {function_name}():
    """
    Acción OCR: Escribir '{text_escaped}' cerca de '{reference_text}'
    
    Busca el elemento '{reference_text}' y escribe
    el texto en una posición relativa.
    """
    from rpa_framework.ocr.engine import OCREngine
    from rpa_framework.ocr.matcher import OCRMatcher
    from rpa_framework.ocr.actions import OCRActions
    
    try:
        engine = OCREngine(
            engine='{self.engine}',
            language='{self.language}',
            confidence_threshold=0.5,
            use_gpu=False
        )
        matcher = OCRMatcher(threshold=80)
        actions = OCRActions(engine, matcher, delay=0.3)
        
        result = actions.type_near_text(
            reference_text='{reference_text}',
            text_to_type='{text_escaped}',
            offset_x={offset_x},
            offset_y={offset_y},
            fuzzy={str(fuzzy).lower()}
        )
        
        return result
    
    except Exception as e:
        return {{
            'action': 'type_near_text',
            'status': 'error',
            'error': str(e),
            'reference': '{reference_text}'
        }}


{module_name} = {function_name}
'''
        
        return {
            'name': module_name,
            'function_name': function_name,
            'code': code,
            'action_type': 'type_near_text',
            'parameters': {
                'reference_text': reference_text,
                'text_to_type': text_to_type,
                'offset_x': offset_x,
                'offset_y': offset_y,
                'fuzzy': fuzzy
            }
        }
    
    def generate_conditional_module(
        self,
        search_terms: List[str],
        true_actions: List[str],
        false_actions: Optional[List[str]] = None,
        module_name: Optional[str] = None
    ) -> Dict:
        """Generar módulo condicional basado en OCR."""
        if not module_name:
            module_name = f"ocr_conditional_{self.generated_count}"
            self.generated_count += 1
        
        function_name = f"execute_{module_name}".replace('-', '_')
        
        search_terms_str = json.dumps(search_terms)
        true_actions_str = json.dumps(true_actions)
        false_actions_str = json.dumps(false_actions or [])
        
        code = f'''# Auto-generated OCR Conditional Module
# Generated: {datetime.now().isoformat()}

def {function_name}():
    """
    Acción OCR: Condicional basado en búsqueda de texto
    
    Si encuentra los textos {search_terms},
    ejecuta acciones true. Si no, ejecuta acciones false.
    """
    from rpa_framework.ocr.engine import OCREngine
    from rpa_framework.ocr.matcher import OCRMatcher
    from rpa_framework.ocr.actions import OCRActions
    
    try:
        engine = OCREngine(
            engine='{self.engine}',
            language='{self.language}',
            confidence_threshold=0.5,
            use_gpu=False
        )
        matcher = OCRMatcher(threshold=80)
        actions = OCRActions(engine, matcher, delay=0.3)
        
        # Buscar uno de los términos
        search_terms = {search_terms_str}
        found = None
        
        for term in search_terms:
            try:
                matches = actions.capture_and_find(term, fuzzy=True)
                if matches:
                    found = matches[0]
                    break
            except:
                pass
        
        result = {{
            'action': 'conditional',
            'found': found is not None,
            'matched_text': found['text'] if found else None
        }}
        
        if found:
            # Ejecutar true actions
            result['executed'] = 'true_actions'
            result['true_actions'] = {true_actions_str}
        else:
            # Ejecutar false actions
            result['executed'] = 'false_actions'
            result['false_actions'] = {false_actions_str}
        
        return result
    
    except Exception as e:
        return {{
            'action': 'conditional',
            'status': 'error',
            'error': str(e)
        }}


{module_name} = {function_name}
'''
        
        return {
            'name': module_name,
            'function_name': function_name,
            'code': code,
            'action_type': 'conditional',
            'parameters': {
                'search_terms': search_terms,
                'true_actions': true_actions,
                'false_actions': false_actions or []
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


# Ejemplo de uso
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    gen = OCRCodeGenerator(engine='easyocr', language='es')
    
    # Generar módulo click
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
