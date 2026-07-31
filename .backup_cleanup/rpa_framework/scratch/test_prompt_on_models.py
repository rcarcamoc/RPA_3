import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent.parent
load_dotenv(ROOT_DIR / ".env", override=True)

sys.path.insert(0, str(ROOT_DIR))
from rpa_framework.utils.llm_config import OPENROUTER_BASE_URL, LLM_DEFAULT_TEMPERATURE, LLM_DEFAULT_MAX_TOKENS, LLM_DEFAULT_TIMEOUT

API_KEY = os.getenv("OPENROUTER_API_KEY", "")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://rpa-framework.local",
}

prompt = """
Eres un experto clínico en interpretación de terminología radiológica y exámenes de imagen.
Tu tarea es determinar si el texto ENCONTRADO (puede tener errores típicos de OCR) 
describe el mismo examen que el BUSCADO.

BUSCADO: "ECOTOMOGRAFÍA DOPPLER VENOSO DE EXTREMIDAD INFERIOR IZQUIERDA"
ENCONTRADO (línea completa OCR): "Examen Hecho Eco Doppler Venoso EE ll Izquierda 09-06-2026 0019341968 Normal E ORNELLA JOS... RODRIGUEZ... 43a9m USIMP. ras. N"

---
## REGLAS DE EQUIVALENCIA (Tolerancia OCR razonable)

1. **ACRÓNIMOS Y MODALIDADES**:
   - RESONANCIA MAGNÉTICA ≈ RM ≈ RMNC ≈ RIM ≈ RNM ≈ RAM ≈ MRI.
   - TOMOGRAFÍA COMPUTADA ≈ TC ≈ TAC ≈ CT ≈ T.C.
   - ULTRASONIDO ≈ ECOTOMOGRAFÍA ≈ ECO ≈ US.
   - RADIOGRAFÍA ≈ RX ≈ R-X.

2. **CORRECCIÓN OCR PERMITIDA** (errores de carácter simples):
   - Un carácter cambiado: "S"↔"5", "I"↔"1"↔"|", "O"↔"0", "B"↔"8".
   - Letras adicionales o faltantes al inicio/fin por segmentación (ej: "TAC" → "TAC ").
   - Acento o ñ incorrectos (ej: "Ecotomografia" ≈ "Ecotomografía").

3. **REGIÓN ANATÓMICA**: debe coincidir en la zona principal.

---
## PROHIBICIONES ESTRICTAS (estas situaciones = es_match: false)

- ❌ NO aceptar si la corrección requiere cambiar MÁS DE 3 caracteres simultáneamente.
- ❌ NO inventar palabras completas: si el OCR dice "Prortario" NO puede ser "TAC Cerebro".
- ❌ NO aceptar si la modalidad (TAC, RM, RX, ECO) no tiene ninguna representation reconocible en el ENCONTRADO.
- ❌ NO aceptar si la región anatómica no coincide en absoluto.
- ❌ NO aceptar si tienes dudas razonables (usa confianza baja → es_match: false).

---
## PROCESO DE RAZONAMIENTO

1. Extrae del ENCONTRADO el segmento que parece el nombre del examen.
2. Aplica corrección OCR MÍNIMA (≤3 caracteres). ¿Qué examen queda?
3. ¿Ese examen equivale al BUSCADO?
4. Si en algún paso necesitaste cambiar palabras enteras, responde es_match: false.

RESPONDE SOLO EN FORMATO JSON:
{
  "es_match": true o false,
  "razonamiento": "Explicación concreta y breve (máx 100 chars)",
  "confianza": 0.0-1.0
}
"""

models_to_test = [
    "google/gemma-4-31b-it:free",
    "openrouter/owl-alpha",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "poolside/laguna-m.1:free"
]

def test_model(model_id):
    print(f"\n--- Testing model: {model_id} ---")
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": LLM_DEFAULT_MAX_TOKENS,
        "temperature": LLM_DEFAULT_TEMPERATURE,
        "reasoning": {"exclude": True}
    }
    try:
        r = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            timeout=LLM_DEFAULT_TIMEOUT,
        )
        print(f"Status Code: {r.status_code}")
        try:
            res = r.json()
            if "choices" in res:
                content = res["choices"][0]["message"].get("content")
                reasoning = res["choices"][0]["message"].get("reasoning")
                print(f"Content:\n{content}")
                if reasoning:
                    print(f"Reasoning:\n{reasoning}")
            else:
                print(json.dumps(res, indent=2))
        except Exception as e:
            print(f"Error parsing response: {e}")
            print(f"Raw body: {r.text[:500]}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    for m in models_to_test:
        test_model(m)
