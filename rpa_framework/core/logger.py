"""
Logger simple para el sistema de workflows.

Proporciona logging tanto a consola como a archivo, con timestamps automáticos.
"""

from datetime import datetime
from typing import List
import os


class WorkflowLogger:
    """Logger simple para workflows"""
    
    def __init__(self, filepath: str = None):
        """
        Inicializa el logger.
        
        Args:
            filepath: Ruta al archivo de log. Si es None, solo logea a consola.
        """
        self.filepath = filepath
        self.logs: List[str] = []
        
        # Asegurar que el directorio existe
        if filepath:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    def log(self, message: str, level: str = "INFO"):
        """
        Registra un mensaje.
        
        Args:
            message: Mensaje a registrar
            level: Nivel del log (INFO, WARNING, ERROR)
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}"
        
        # Guardar en memoria
        self.logs.append(log_entry)
        
        # Imprimir a consola
        print(log_entry)
        
        # Guardar en archivo
        if self.filepath:
            try:
                with open(self.filepath, 'a', encoding='utf-8') as f:
                    f.write(log_entry + '\n')
            except Exception as e:
                print(f"Error escribiendo log: {e}")
    
    def info(self, message: str):
        """Log de nivel INFO"""
        self.log(message, "INFO")
    
    def warning(self, message: str):
        """Log de nivel WARNING"""
        self.log(message, "WARNING")
    
    def error(self, message: str):
        """Log de nivel ERROR"""
        self.log(message, "ERROR")
    
    def get_logs(self) -> List[str]:
        """Devuelve todos los logs registrados"""
        return self.logs.copy()
    
    def clear_logs(self):
        """Limpia los logs en memoria"""
        self.logs.clear()
    
    def get_recent_logs(self, count: int = 100) -> List[str]:
        """
        Devuelve los últimos N logs.
        
        Args:
            count: Número de logs a devolver
            
        Returns:
            Lista con los últimos N logs
        """
        return self.logs[-count:] if len(self.logs) > count else self.logs.copy()
