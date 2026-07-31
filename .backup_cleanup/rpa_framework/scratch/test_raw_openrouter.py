import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent.parent
load_dotenv(ROOT_DIR / ".env", override=True)

API_KEY = os.getenv("OPENROUTER_API_KEY", "")
BASE_URL = "https://openrouter.ai/api/v1"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://rpa-framework.local",
}

models_to_test = [
    "google/gemma-4-31b-it:free",
    "qwen/qwen3-235b-a22b-thinking-2507",
    "meta-llama/llama-3.3-70b-instruct:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "moonshotai/kimi-k2.6:free",
    "z-ai/glm-4.5-air:free",
    "stepfun/step-3.5-flash:free",
    "google/gemma-3-27b-it:free",
]

def test_model(model_id):
    print(f"\n--- Testing model: {model_id} ---")
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Di solo la palabra: OK"}],
        "max_tokens": 15,
        "temperature": 0.0,
    }
    try:
        r = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            timeout=20,
        )
        print(f"Status Code: {r.status_code}")
        try:
            response_json = r.json()
            print(json.dumps(response_json, indent=2))
        except Exception as e:
            print(f"Failed to parse JSON: {e}")
            print(f"Raw body: {r.text[:500]}")
    except Exception as e:
        print(f"Exception during request: {e}")

if __name__ == "__main__":
    for m in models_to_test:
        test_model(m)
