import requests
import json
import os
from dotenv import load_dotenv

load_dotenv('c:/Desarrollo/RPA_3/.env')
api_key = os.getenv('OPENROUTER_API_KEY')

response = requests.post(
    'https://openrouter.ai/api/v1/chat/completions',
    headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
    json={
        'model': 'nvidia/nemotron-3-nano-30b-a3b:free',
        'messages': [{'role': 'user', 'content': 'Test'}]
    }
)
print('Status:', response.status_code)
print('Body:', response.text)
