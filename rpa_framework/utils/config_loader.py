"""Carga configuración YAML."""
import yaml
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def load_config(config_file: str) -> dict:
    """Carga YAML config."""
    config_path = Path(config_file)
    
    if not config_path.exists():
        logger.warning(f"Config no encontrada: {config_file}")
        return {}
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        logger.info(f"Config cargada: {config_file}")
        return config or {}
    except Exception as e:
        logger.error(f"Error cargando config: {e}")
        return {}
