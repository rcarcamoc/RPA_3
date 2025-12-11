"""Logging estructurado."""
import logging
from pathlib import Path

def setup_logging(level: str = "INFO"):
    """Configura logging."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_format = "%(asctime)s [%(name)s] %(levelname)s %(message)s"
    
    logging.basicConfig(
        level=getattr(logging, level),
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "rpa.log", encoding="utf-8")
        ]
    )
