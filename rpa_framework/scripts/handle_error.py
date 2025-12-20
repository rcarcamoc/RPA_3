"""
Script para manejar errores.
"""
import json
import os

error_message = os.getenv('message', 'Error desconocido')
print(f"[Handle Error] Manejando error: {error_message}")

result = {
    "error_handled": True,
    "recovery_action": "notified_admin",
    "final_status": "failed_with_recovery"
}

print(json.dumps(result))
