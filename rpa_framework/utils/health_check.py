"""Health checks."""
import logging
import psutil

logger = logging.getLogger(__name__)

class SystemMonitor:
    """Monitorea salud del sistema."""
    
    @staticmethod
    def check():
        """Verifica CPU, RAM, disco."""
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        
        if cpu > 80:
            logger.warning(f"CPU alta: {cpu}%")
        if ram > 80:
            logger.warning(f"RAM alta: {ram}%")
        
        logger.debug(f"CPU: {cpu}%, RAM: {ram}%")
        return {"cpu": cpu, "ram": ram}
