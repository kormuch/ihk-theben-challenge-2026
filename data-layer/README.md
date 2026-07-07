# Thebenpaul Data Layer

## OCR / Image support

The backend uses Tesseract OCR (via pytesseract + Pillow) for:
- **Image files** (PNG, JPG, TIFF, BMP, WEBP) — direct OCR text extraction
- **Scanned PDFs** — automatic OCR fallback when pdfplumber finds no text

Languages installed: German (`deu`) + English (`eng`).

The Dockerfile installs `tesseract-ocr`, `tesseract-ocr-deu`, and `tesseract-ocr-eng`. For local development outside Docker, install Tesseract separately:
- Windows: `winget install UB-Mannheim.TesseractOCR`
- macOS: `brew install tesseract tesseract-lang`
- Linux: `apt install tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng`

## Product-Layer export

The endpoint `GET /api/v1/export/products.json` exports all products in product-layer format (schema version `0.1.0`). It is automatically called when products are confirmed via `/api/v1/analyze/confirm` and writes to the shared volume at `PRODUCT_LAYER_DATA_DIR` (default: `/product-layer-data`).

Family mapping (data-layer → product-layer):
- Timer → Time Switch
- Motion Sensor → Motion Detector
- Room Thermostat → HVAC Controller
- KNX Actuator → KNX Actuator
- Energy Meter → Energy Meter

## LLM agent configuration

Document analysis uses config-as-code from:

```bash
config/llm_agents.json
```

The backend reads this path from `DATA_LAYER_LLM_CONFIG`. In Docker Compose it is mounted read-only at `/config/llm_agents.json`.

By default, the data layer uses the same LAN Ollama pattern as the product layer:

```bash
DATA_LAYER_LLM_CHAIN=local_ollama_lan
```

Use `DATA_LAYER_LLM_CHAIN` to select a provider chain:

- `local_ollama_lan`: Ollama LAN only. This is the default.
- `analysis_default`: alias for Ollama LAN only.
- `local_only`: backwards-compatible alias for Ollama LAN only.
- `enterprise_deepseek_existing`: DeepSeek only, for environments with existing approved DeepSeek access.
- `enterprise_cloud_fallback`: Ollama LAN first, then approved external fallbacks.
- `certification_expert`: environment-local certification expert first, then general fallback providers.

Secrets are not stored in JSON. Add real keys in `.env`, Docker secrets, or CI secrets:

```bash
OLLAMA_API_KEY=
OLLAMA_CERTIFICATION_API_KEY=
DEEPSEEK_API_KEY=
GEMINI_API_KEY=
GROQ_API_KEY=
```

To add an environment-specific LLM agent, add a provider under `providers`, add its id to a chain, and set any required API key through its `api_key_env`. For Ollama over LAN, use provider type `ollama_generate` with `base_url`, `endpoint`, and `model`.

Alternative DeepSeek setup for an enterprise environment that already has approved DeepSeek access:

```bash
DATA_LAYER_LLM_CHAIN=enterprise_deepseek_existing
DEEPSEEK_API_KEY=your-secret-from-env-docker-secret-or-ci-secret
```

Then enable the `deepseek` provider in `config/llm_agents.json`:

```json
{
  "providers": {
    "deepseek": {
      "enabled": true
    }
  }
}
```

Keep this as an environment decision. The lakehouse architecture stays generic: provider choice is externalized, while data products, metadata, lineage, classification, and access rules remain governed centrally across modules.

The same file also contains `request_examples` with concrete API payloads and curl examples for:

- `ollama_lan`
- `ollama_certification_expert`
- `deepseek`
- `gemini`
- `groq`

The old error:

```text
Classification failed: No API key configured (DEEPSEEK_API_KEY, GEMINI_API_KEY, or GROQ_API_KEY)
```

is replaced by a config-driven provider chain. If no provider is usable, the backend now reports the configured env vars and the last provider error.
