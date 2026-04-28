import os
import time
import logging
from pathlib import Path
from PyQt6.QtCore import QTimer, QDateTime

logger = logging.getLogger(__name__)

def cleanup_old_logs(log_root="log", hours=24):
    """
    Elimina archivos de imagen (.png, .jpg, .jpeg) en la carpeta log 
    y subcarpetas que tengan más de 'hours' de antigüedad.
    """
    try:
        now = time.time()
        cutoff = now - (hours * 3600)
        count = 0
        
        log_path = Path(log_root)
        if not log_path.exists():
            return 0
            
        extensions = {'.png', '.jpg', '.jpeg', '.bmp'}
        
        for root, dirs, files in os.walk(log_path):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in extensions:
                    file_time = file_path.stat().st_mtime
                    if file_time < cutoff:
                        try:
                            file_path.unlink()
                            count += 1
                        except Exception as e:
                            logger.error(f"No se pudo eliminar {file_path}: {e}")
        
        if count > 0:
            logger.info(f"🧹 Limpieza de logs completada: {count} imágenes eliminadas (> {hours}h).")
        return count
    except Exception as e:
        logger.error(f"Error en limpieza de logs: {e}")
        return 0

class PeriodicCleanup:
    """Clase para manejar la limpieza periódica alineada con el reloj."""
    def __init__(self, log_root="log", hours=24):
        self.log_root = log_root
        self.hours = hours
        self.timer = QTimer()
        self.timer.timeout.connect(self._check_time)
        # Verificamos cada minuto si es "en punto"
        self.timer.start(60000) 
        
    def _check_time(self):
        current_time = QDateTime.currentDateTime().time()
        # Si estamos en el primer minuto de cualquier hora (0, 1, 2...)
        if current_time.minute() == 0:
            cleanup_old_logs(self.log_root, self.hours)
