"""
Plantilla de Script para Workflow Engine
=========================================

Este archivo sirve como plantilla para crear scripts que se ejecutan
en el workflow engine del RPA Framework 3.

USO:
1. Copia este archivo a scripts/mi_script.py
2. Modifica la lógica según tu necesidad
3. Referéncialo en un nodo ACTION o LOOP

IMPORTANTE:
- La última línea de output debe ser JSON válido
- Las variables se pasan via os.environ
- El script debe devolver código 0 para éxito
"""

import json
import os
import sys

def main():
    """
    Función principal del script.
    Retorna un diccionario con las variables a actualizar.
    """
    
    # ======================
    # 1. LEER VARIABLES
    # ======================
    # Las variables del workflow se pasan como variables de entorno
    
    # Variable simple
    username = os.getenv('username', 'default_user')
    
    # Variable numérica (siempre llega como string)
    max_retries = int(os.getenv('max_retries', '3'))
    
    # Variable JSON (si pasaste un objeto)
    # items_json = os.getenv('items', '[]')
    # items = json.loads(items_json)
    
    # Variable de loop (si estás en un LOOP)
    loop_index = int(os.getenv('_loop_index', '0'))
    
    # Debug (puedes imprimir antes del JSON final)
    print(f"[DEBUG] Usuario: {username}")
    print(f"[DEBUG] Iteración: {loop_index}")
    
    # ======================
    # 2. TU LÓGICA AQUÍ
    # ======================
    
    # Ejemplo: simular algún procesamiento
    resultado = f"Procesado por {username}"
    exito = True  # o False si hay error
    
    # Ejemplo con condición
    if loop_index > 5:
        exito = False
        resultado = "Demasiadas iteraciones"
    
    # ======================
    # 3. RETORNAR RESULTADO
    # ======================
    # IMPORTANTE: La última línea debe ser JSON puro
    # Esto actualiza el contexto del workflow
    
    output = {
        "resultado": resultado,
        "status": "success" if exito else "failed",
        "procesado_en_iteracion": loop_index
    }
    
    # Imprimir JSON (será parseado por el executor)
    print(json.dumps(output))
    
    # Código de salida
    return 0 if exito else 1


if __name__ == "__main__":
    sys.exit(main())
