"""
Script de ejemplo para procesar éxito.
"""
import json
import os

session_token = os.getenv('session_token', 'none')

print(f"[Success Script] Sesión iniciada correctamente con token: {session_token}", flush=True)

result = {
    "process_status": "completed",
    "message": "Login successful, proceeding with workflow"
}

print(json.dumps(result))
