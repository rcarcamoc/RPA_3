import requests
import json
import os
from dotenv import load_dotenv

load_dotenv('c:/Desarrollo/RPA_3/.env')
api_key = os.getenv('OPENROUTER_API_KEY')
if not api_key:
    print('No API key found')
    exit()

response = requests.get('https://openrouter.ai/api/v1/models')
models = response.json().get('data', [])
free_models = [m['id'] for m in models if m.get('pricing', {}).get('prompt') == '0' and m.get('pricing', {}).get('completion') == '0']

print("Free models available:")
for m in free_models:
    if 'nvidia' in m or 'nemotron' in m or 'arcee' in m or 'trinity' in m:
        print(f" - {m}")
