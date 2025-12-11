"""ActionOptimizer - Limpia acciones."""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class ActionOptimizer:
    """Optimiza acciones (limpieza, consolidación)."""
    
    @staticmethod
    def optimize(actions: List[Dict]) -> List[Dict]:
        """Optimiza lista de acciones."""
        if not actions:
            return []
        
        optimized = []
        
        for action in actions:
            # Saltar acciones de movimiento sin click
            if action.get("type") == "move":
                continue
            
            optimized.append(action)
        
        logger.info(f"Acciones: {len(actions)} → {len(optimized)}")
        return optimized
