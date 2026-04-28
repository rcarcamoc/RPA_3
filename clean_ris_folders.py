import os
import shutil
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clean_ris_directories():
    target_path = r"C:\Users\Operaciones\AppData\Roaming\IsolatedStorage\RIS"
    prefixes = ("11.0", "11.3")
    
    if not os.path.exists(target_path):
        logging.error(f"La ruta no existe: {target_path}")
        return

    logging.info(f"Escaneando directorio: {target_path}")
    
    try:
        items = os.listdir(target_path)
        deleted_count = 0
        
        for item in items:
            item_path = os.path.join(target_path, item)
            
            # Verificar si es un directorio y si comienza con los prefijos indicados
            if os.path.isdir(item_path) and item.startswith(prefixes):
                try:
                    logging.info(f"Eliminando carpeta: {item}")
                    shutil.rmtree(item_path)
                    deleted_count += 1
                except Exception as e:
                    logging.error(f"No se pudo eliminar {item}: {e}")
        
        if deleted_count == 0:
            logging.info("No se encontraron carpetas que coincidan con los criterios.")
        else:
            logging.info(f"Limpieza completada. Se eliminaron {deleted_count} carpetas.")
            
    except Exception as e:
        logging.error(f"Error al listar el directorio: {e}")

if __name__ == "__main__":
    clean_ris_directories()
