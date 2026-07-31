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

prompt = "Di solo la palabra: OK"

models_to_test = [
    "openrouter/owl-alpha",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "poolside/laguna-m.1:free",
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "google/gemma-4-31b-it:free"
]

def test_model(model_id):
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 50,
        "temperature": 0.0,
    }
    try:
        r = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            timeout=10,
        )
        print(f"{model_id:<55} | Status: {r.status_code} | ", end="")
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"].get("content", "").strip().replace("\n", " ")
            print(f"✅ OK - Response: '{content}'")
        else:
            try:
                err = r.json().get("error", {}).get("message", "Error")[:100]
            except Exception:
                err = r.text[:100]
            print(f"❌ Error: {err}")
    except Exception as e:
        print(f"{model_id:<55} | Exception: {e}")

if __name__ == "__main__":
    print(f"Testing {len(models_to_test)} models...")
    for m in models_to_test:
        test_model(m)
