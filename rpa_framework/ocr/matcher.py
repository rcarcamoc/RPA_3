# rpa_framework/ocr/matcher.py

import re
from typing import List, Dict, Optional, Tuple
from fuzzywuzzy import fuzz
import logging

logger = logging.getLogger(__name__)


class OCRMatcher:
    """
    Motor de búsqueda y matching para resultados OCR.
    
    Soporta:
    - Búsqueda fuzzy (tolerancia a errores)
    - Búsqueda exacta
    - Búsqueda por patrón (regex)
    """
    
    def __init__(self, threshold: int = 80):
        """
        Inicializar matcher.
        
        Args:
            threshold: Umbral mínimo de similitud (0-100)
        """
        self.threshold = threshold
        logger.info(f"OCRMatcher inicializado (threshold: {threshold})")
    
    def find_text(
        self,
        text_list: List[Dict],
        search_term: str,
        fuzzy: bool = True,
        case_sensitive: bool = False,
        return_all: bool = False
    ) -> List[Dict]:
        """
        Busca un término en resultados OCR.
        
        Args:
            text_list: Lista de resultados OCR del engine
            search_term: Texto a buscar
            fuzzy: Usar búsqueda fuzzy (tolerancia a errores)
            case_sensitive: Distinguir mayúsculas/minúsculas
            return_all: Retornar todos los matches (no solo el mejor)
        
        Returns:
            Lista de matches ordenada por similitud
        """
        if not text_list:
            return []
        
        matches = []
        search_norm = search_term if case_sensitive else search_term.lower()
        
        for text_data in text_list:
            text = text_data['text']
            text_norm = text if case_sensitive else text.lower()
            
            if fuzzy:
                # Búsqueda fuzzy con múltiples estrategias
                similarity = self._fuzzy_match(search_norm, text_norm)
                
                if similarity >= self.threshold:
                    # Calcular similitud exacta como desempate
                    exact_similarity = fuzz.ratio(search_norm, text_norm)
                    
                    match = {
                        **text_data,
                        'match_similarity': similarity,
                        'exact_similarity': exact_similarity,
                        'match_type': 'fuzzy',
                        'search_term': search_term
                    }
                    matches.append(match)
                    logger.debug(f"Fuzzy match: '{text}' (similarity: {similarity}%, exact: {exact_similarity}%)")
            
            else:
                # Búsqueda exacta (substring)
                if search_norm in text_norm:
                    # Calcular ratio también para exacta
                    exact_similarity = fuzz.ratio(search_norm, text_norm)
                    
                    match = {
                        **text_data,
                        'match_similarity': 100,
                        'exact_similarity': exact_similarity,
                        'match_type': 'exact',
                        'search_term': search_term
                    }
                    matches.append(match)
                    logger.debug(f"Exact match: '{text}'")
        
        # Ordenar por similitud fuzzy descendente, y luego por similitud exacta
        matches.sort(key=lambda x: (x['match_similarity'], x.get('exact_similarity', 0)), reverse=True)
        
        if not return_all and matches:
            return [matches[0]]  # Retornar solo el mejor match
        
        logger.info(f"Encontrados {len(matches)} matches para '{search_term}'")
        return matches
    
    def _fuzzy_match(self, term1: str, term2: str) -> int:
        """
        Calcular similitud fuzzy entre dos términos.
        
        Usa múltiples algoritmos y retorna el máximo.
        """
        # Usar token_set_ratio para ignorar orden de palabras
        ratio1 = fuzz.token_set_ratio(term1, term2)
        # Usar partial_ratio para búsqueda de substrings
        ratio2 = fuzz.partial_ratio(term1, term2)
        # Usar ratio estándar
        ratio3 = fuzz.ratio(term1, term2)
        
        # Retornar el máximo
        return max(ratio1, ratio2, ratio3)
    
    def find_by_pattern(
        self,
        text_list: List[Dict],
        pattern: str,
        flags: int = 0
    ) -> List[Dict]:
        """
        Busca por patrón regex.
        
        Útil para:
        - Emails: r'[\\w\\.-]+@[\\w\\.-]+\\.\\w+'
        - Teléfonos: r'\\d{7,}'
        - Fechas: r'\\d{1,2}/\\d{1,2}/\\d{4}'
        - URLs: r'https?://[^\\s]+'
        
        Args:
            text_list: Resultados OCR
            pattern: Patrón regex
            flags: Flags de regex (re.IGNORECASE, etc)
        
        Returns:
            Lista de matches
        """
        matches = []
        
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            logger.error(f"Patrón regex inválido: {e}")
            return []
        
        for text_data in text_list:
            if regex.search(text_data['text']):
                match = {
                    **text_data,
                    'match_type': 'pattern',
                    'pattern': pattern,
                    'match_similarity': 100
                }
                matches.append(match)
                logger.debug(f"Pattern match: '{text_data['text']}'")
        
        logger.info(f"Encontrados {len(matches)} matches para patrón: {pattern}")
        return matches
    
    def find_multiple(
        self,
        text_list: List[Dict],
        search_terms: List[str],
        fuzzy: bool = True,
        case_sensitive: bool = False
    ) -> Dict[str, List[Dict]]:
        """
        Busca múltiples términos a la vez.
        
        Args:
            text_list: Resultados OCR
            search_terms: Lista de términos a buscar
            fuzzy: Usar búsqueda fuzzy
            case_sensitive: Distinguir mayúsculas/minúsculas
        
        Returns:
            Dict con {search_term: [matches]}
        """
        results = {}
        
        for term in search_terms:
            results[term] = self.find_text(
                text_list,
                term,
                fuzzy=fuzzy,
                case_sensitive=case_sensitive,
                return_all=True
            )
        
        return results
    
    def find_nearest(
        self,
        text_list: List[Dict],
        search_term: str,
        reference_point: Tuple[float, float],
        fuzzy: bool = True,
        case_sensitive: bool = False,
        max_distance: Optional[float] = None
    ) -> Optional[Dict]:
        """
        Busca texto más cercano a un punto de referencia.
        
        Útil para casos donde hay múltiples matches
        y necesitas el más cercano a un elemento.
        
        Args:
            text_list: Resultados OCR
            search_term: Texto a buscar
            reference_point: (x, y) punto de referencia
            fuzzy: Usar búsqueda fuzzy
            case_sensitive: Distinguir mayúsculas/minúsculas
            max_distance: Distancia máxima permitida (en píxeles)
        
        Returns:
            Match más cercano o None
        """
        matches = self.find_text(
            text_list,
            search_term,
            fuzzy=fuzzy,
            case_sensitive=case_sensitive,
            return_all=True
        )
        
        if not matches:
            return None
        
        ref_x, ref_y = reference_point
        
        # Calcular distancia a cada match
        for match in matches:
            center = match['center']
            distance = ((center['x'] - ref_x) ** 2 + (center['y'] - ref_y) ** 2) ** 0.5
            match['distance_to_reference'] = distance
        
        # Filtrar por distancia máxima si se especifica
        if max_distance:
            matches = [m for m in matches if m['distance_to_reference'] <= max_distance]
        
        if not matches:
            return None
        
        # Retornar el más cercano
        nearest = min(matches, key=lambda x: x['distance_to_reference'])
        logger.info(f"Nearest match encontrado a {nearest['distance_to_reference']:.0f}px")
        return nearest
    
    def find_in_region(
        self,
        text_list: List[Dict],
        search_term: str,
        region: Dict,
        fuzzy: bool = True,
        case_sensitive: bool = False
    ) -> List[Dict]:
        """
        Busca texto dentro de una región específica.
        
        Args:
            text_list: Resultados OCR
            search_term: Texto a buscar
            region: Dict con {'x_min', 'y_min', 'x_max', 'y_max'}
            fuzzy: Usar búsqueda fuzzy
            case_sensitive: Distinguir mayúsculas/minúsculas
        
        Returns:
            Matches dentro de la región
        """
        matches = self.find_text(
            text_list,
            search_term,
            fuzzy=fuzzy,
            case_sensitive=case_sensitive,
            return_all=True
        )
        
        # Filtrar por región
        filtered = []
        for match in matches:
            bounds = match['bounds']
            
            # Verificar si el centro está dentro de la región
            center_x = match['center']['x']
            center_y = match['center']['y']
            
            if (region['x_min'] <= center_x <= region['x_max'] and
                region['y_min'] <= center_y <= region['y_max']):
                filtered.append(match)
        
        logger.info(f"Encontrados {len(filtered)} matches en región")
        return filtered
    
    def set_threshold(self, threshold: int):
        """Cambiar umbral de similitud dinámicamente"""
        if not 0 <= threshold <= 100:
            raise ValueError("Threshold debe estar entre 0 y 100")
        self.threshold = threshold
        logger.info(f"Threshold actualizado a {threshold}")


# Ejemplo de uso
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    
    # Simular resultados OCR
    mock_ocr_results = [
        {
            'text': 'Enviar',
            'confidence': 0.95,
            'center': {'x': 100, 'y': 50},
            'bounds': {'x_min': 80, 'y_min': 40, 'x_max': 120, 'y_max': 60}
        },
        {
            'text': 'Envío',
            'confidence': 0.92,
            'center': {'x': 200, 'y': 50},
            'bounds': {'x_min': 180, 'y_min': 40, 'x_max': 220, 'y_max': 60}
        },
        {
            'text': 'Cancelar',
            'confidence': 0.98,
            'center': {'x': 300, 'y': 50},
            'bounds': {'x_min': 280, 'y_min': 40, 'x_max': 320, 'y_max': 60}
        }
    ]
    
    matcher = OCRMatcher(threshold=75)
    
    # Búsqueda fuzzy
    matches = matcher.find_text(mock_ocr_results, "Enviar", fuzzy=True)
    print(f"Fuzzy matches: {len(matches)}")
    for m in matches:
        print(f"  - {m['text']} (similitud: {m['match_similarity']}%)")
    
    # Búsqueda por patrón
    pattern_matches = matcher.find_by_pattern(mock_ocr_results, r'^Env.*')
    print(f"Pattern matches: {len(pattern_matches)}")
