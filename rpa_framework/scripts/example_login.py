"""
Script de ejemplo para simular un login.
Retorna JSON con el resultado en stdout.
"""
import json
import os
import random

# Obtener variables del workflow
username = os.getenv('username', 'default')

print(f"[Example Login Script] Usuario: {username}", flush=True)

# Simular login (60% de éxito)
success = random.random() > 0.4

if success:
    result = {
        "login_status": "success",
        "user_id": 123,
        "session_token": "abc123xyz"
    }
else:
    result = {
        "login_status": "failed",
        "error_message": "Invalid credentials"
    }

# Retornar JSON para actualizar el contexto del workflow
print(json.dumps(result))
