# Configuración de Variables de Entorno

Este proyecto utiliza variables de entorno para gestionar información sensible como API keys.

## Configuración Inicial

1. **Copia el archivo de ejemplo:**
   ```bash
   cp .env.example .env
   ```

2. **Edita el archivo `.env` y completa con tus valores reales:**
   ```
   OPENROUTER_API_KEY=tu_api_key_real_aqui
   ```

3. **Asegúrate de que `.env` esté en `.gitignore`** (ya está configurado)

## Variables Disponibles

### OPENROUTER_API_KEY
- **Descripción:** API Key para acceder a OpenRouter (servicio de LLM)
- **Obtener en:** https://openrouter.ai/
- **Usado en:**
  - `rpa_framework/recordings/ocr/busqueda_triple_text_only.py`
  - `rpa_framework/recordings/web/detecta_patologia_ia.py`

## Notas de Seguridad

- ⚠️ **NUNCA** subas el archivo `.env` al repositorio
- ⚠️ **NUNCA** compartas tus API keys públicamente
- ✅ El archivo `.env` está protegido por `.gitignore`
- ✅ Usa `.env.example` como plantilla para compartir con el equipo

## Dependencias

Este proyecto usa `python-dotenv` para cargar las variables de entorno:

```bash
pip install python-dotenv
```
