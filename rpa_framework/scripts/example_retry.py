"""
Script de ejemplo para reintentos en loop.
"""
import json
import os

retry_count = os.getenv('retry_count', '0')

print(f"[Retry Script] Reintentando login... (intento {retry_count})", flush=True)

result = {
    "retry_attempt": int(retry_count),
    "message": f"Retry attempt {retry_count}"
}

print(json.dumps(result))
