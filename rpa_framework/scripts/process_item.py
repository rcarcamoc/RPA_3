"""
Script para procesar un item individual en el loop.
"""
import json
import os
import time

current_index = os.getenv('current_index', '0')
items = os.getenv('items', '[]')

print(f"[Process Item] Procesando item #{current_index}")

# Simular procesamiento
time.sleep(0.1)  # Pequeña pausa para simular trabajo

result = {
    "processed_index": int(current_index),
    "status": "processed"
}

print(json.dumps(result))
