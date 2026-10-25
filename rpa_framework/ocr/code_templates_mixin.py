# -*- coding: utf-8 -*-
"""
Mixin con plantillas de generación de código Python para acciones OCR secundarias
(doble click, click derecho, copiar, seleccionar, escribir, condicional, hover y espera).
Extraído de rpa_framework/ocr/code_generator.py.
"""

import json
from typing import Dict, List, Optional
from datetime import datetime


class OCRCodeTemplatesMixin:
    """Mixin con métodos generadores de módulos Python para OCRCodeGenerator."""

    def generate_double_click_module(
        self,
        text_to_find: str,
        offset_x: int = 0,
        offset_y: int = 0,
        fuzzy: bool = True,
        module_name: Optional[str] = None
    ) -> Dict:
        """Generar módulo para double click."""
        if not module_name:
            module_name = f"ocr_double_click_{self.generated_count}"
            self.generated_count += 1
            
        function_name = f"execute_{module_name}".replace('-', '_')
        
        code = f'''# Auto-generated OCR Double Click Module
# Generated: {datetime.now().isoformat()}

def {function_name}():
    """
    Acción OCR: Doble Click en texto '{text_to_find}'
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
        engine = OCREngine(
            engine='{self.engine}',
            language='{self.language}',
            confidence_threshold=0.5,
            use_gpu=True
        )
        matcher = OCRMatcher(threshold=80)
        actions = OCRActions(engine, matcher, delay=0.3)
        
        result = actions.double_click_on_text(
            search_term='{text_to_find}',
            offset_x={offset_x},
            offset_y={offset_y},
            fuzzy={str(fuzzy)}
        )
        
        db_update_status('En Proceso')
        return result
    
    except Exception as e:
        db_update_status('error')
        return {{
            'action': 'double_click',
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
            'action_type': 'double_click',
            'parameters': {'text_to_find': text_to_find}
        }

    def generate_right_click_module(
        self,
        text_to_find: str,
        offset_x: int = 0,
        offset_y: int = 0,
        fuzzy: bool = True,
        module_name: Optional[str] = None
    ) -> Dict:
        """Generar módulo para click derecho."""
        if not module_name:
            module_name = f"ocr_rclick_{self.generated_count}"
            self.generated_count += 1
            
        function_name = f"execute_{module_name}".replace('-', '_')
        
        code = f'''# Auto-generated OCR Right Click Module
# Generated: {datetime.now().isoformat()}

def {function_name}():
    """
    Acción OCR: Click Derecho en texto '{text_to_find}'
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
        engine = OCREngine(
            engine='{self.engine}',
            language='{self.language}',
            confidence_threshold=0.5,
            use_gpu=True
        )
        matcher = OCRMatcher(threshold=80)
        actions = OCRActions(engine, matcher, delay=0.3)
        
        result = actions.right_click_on_text(
            search_term='{text_to_find}',
            offset_x={offset_x},
            offset_y={offset_y},
            fuzzy={str(fuzzy)}
        )
        
        db_update_status('En Proceso')
        return result
    
    except Exception as e:
        db_update_status('error')
        return {{
            'action': 'right_click',
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
            'action_type': 'right_click',
            'parameters': {'text_to_find': text_to_find}
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
        result = actions.copy_text_by_ocr(
            search_term='{text_to_find}',
            fuzzy={str(fuzzy)},
            case_sensitive={str(case_sensitive)}
        )
        
        db_update_status('En Proceso')
        return result
    
    except Exception as e:
        db_update_status('error')
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
    import sys
    import os
    # Add framework root to path to allow importing 'ocr'
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

    from ocr.engine import OCREngine
    from ocr.matcher import OCRMatcher
    from ocr.actions import OCRActions
    
    {self._get_db_tracking_code(module_name)}
    try:
        engine = OCREngine(
            engine='{self.engine}',
            language='{self.language}',
            confidence_threshold=0.5,
            use_gpu=True
        )
        matcher = OCRMatcher(threshold=80)
        actions = OCRActions(engine, matcher, delay=0.3)
        
        result = actions.select_text(
            search_term='{text_to_find}',
            fuzzy={str(fuzzy)}
        )
        
        db_update_status('En Proceso')
        return result
    
    except Exception as e:
        db_update_status('error')
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
        text_escaped = text_to_type.replace("'", "\\'")
        
        code = f'''# Auto-generated OCR Type Module
# Generated: {datetime.now().isoformat()}

def {function_name}():
    """
    Acción OCR: Escribir '{text_escaped}' cerca de '{reference_text}'
    
    Busca el elemento '{reference_text}' y escribe
    el texto en una posición relativa.
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
        engine = OCREngine(
            engine='{self.engine}',
            language='{self.language}',
            confidence_threshold=0.5,
            use_gpu=True
        )
        matcher = OCRMatcher(threshold=80)
        actions = OCRActions(engine, matcher, delay=0.3)
        
        result = actions.type_near_text(
            reference_text='{reference_text}',
            text_to_type='{text_escaped}',
            offset_x={offset_x},
            offset_y={offset_y},
            fuzzy={str(fuzzy)}
        )
        
        db_update_status('En Proceso')
        return result
    
    except Exception as e:
        db_update_status('error')
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
    import sys
    import os
    # Add framework root to path to allow importing 'ocr'
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

    from ocr.engine import OCREngine
    from ocr.matcher import OCRMatcher
    from ocr.actions import OCRActions
    
    {self._get_db_tracking_code(module_name)}
    try:
        engine = OCREngine(
            engine='{self.engine}',
            language='{self.language}',
            confidence_threshold=0.5,
            use_gpu=True
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
            result['executed'] = 'true_actions'
            result['true_actions'] = {true_actions_str}
        else:
            result['executed'] = 'false_actions'
            result['false_actions'] = {false_actions_str}
        
        db_update_status('En Proceso')
        return result
    
    except Exception as e:
        db_update_status('error')
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

    def generate_hover_module(
        self,
        text_to_find: str,
        offset_x: int = 0,
        offset_y: int = 0,
        fuzzy: bool = True,
        module_name: Optional[str] = None
    ) -> Dict:
        """Generar módulo para hover."""
        if not module_name:
            module_name = f"ocr_hover_{self.generated_count}"
            self.generated_count += 1
            
        function_name = f"execute_{module_name}".replace('-', '_')
        
        code = f'''# Auto-generated OCR Hover Module
# Generated: {datetime.now().isoformat()}

def {function_name}():
    """
    Acción OCR: Hover sobre texto '{text_to_find}'
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
        engine = OCREngine(
            engine='{self.engine}',
            language='{self.language}',
            confidence_threshold=0.5,
            use_gpu=True
        )
        matcher = OCRMatcher(threshold=80)
        actions = OCRActions(engine, matcher, delay=0.3)
        
        result = actions.hover_on_text(
            search_term='{text_to_find}',
            offset_x={offset_x},
            offset_y={offset_y},
            fuzzy={str(fuzzy)}
        )
        
        db_update_status('En Proceso')
        return result
    
    except Exception as e:
        db_update_status('error')
        return {{
            'action': 'hover',
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
            'action_type': 'hover',
            'parameters': {'text_to_find': text_to_find}
        }

    def generate_wait_module(
        self,
        text_to_find: str,
        timeout: int = 10,
        fuzzy: bool = True,
        module_name: Optional[str] = None
    ) -> Dict:
        """Generar módulo para esperar texto."""
        if not module_name:
            module_name = f"ocr_wait_{self.generated_count}"
            self.generated_count += 1
            
        function_name = f"execute_{module_name}".replace('-', '_')
        
        code = f'''# Auto-generated OCR Wait Module
# Generated: {datetime.now().isoformat()}

def {function_name}():
    """
    Acción OCR: Esperar texto '{text_to_find}' (Timeout: {timeout}s)
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
        engine = OCREngine(
            engine='{self.engine}',
            language='{self.language}',
            confidence_threshold=0.5,
            use_gpu=True
        )
        matcher = OCRMatcher(threshold=80)
        actions = OCRActions(engine, matcher, delay=0.3)
        
        result = actions.wait_for_text(
            search_term='{text_to_find}',
            timeout={timeout},
            fuzzy={str(fuzzy)}
        )
        
        db_update_status('En Proceso')
        return result
    
    except Exception as e:
        db_update_status('error')
        return {{
            'action': 'wait_for_text',
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
            'action_type': 'wait_for_text',
            'parameters': {'text_to_find': text_to_find}
        }
