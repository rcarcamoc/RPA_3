"""
Script para cargar datos de ejemplo.
"""
import json
import os
import random

data_source = os.getenv('data_source', 'input.csv')
print(f"[Load Data] Cargando datos desde: {data_source}")

# Simular carga de datos
items = ["item_1", "item_2", "item_3", "item_4", "item_5"]
data_valid = random.random() > 0.3  # 70% de exito

result = {
    "data_valid": data_valid,
    "item_count": len(items) if data_valid else 0,
    "items": items if data_valid else [],
    "message": "Datos cargados correctamente" if data_valid else "Error al cargar datos"
}

print(json.dumps(result))
