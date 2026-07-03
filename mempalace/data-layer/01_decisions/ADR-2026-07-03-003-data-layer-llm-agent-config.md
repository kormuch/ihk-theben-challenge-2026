# ADR-2026-07-03-003 - Data-layer LLM agent configuration

## Context
Data-layer document classification failed when no cloud provider API key was configured: `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, or `GROQ_API_KEY`. The project needs environment-specific LLM agents, including LAN-accessible Ollama and optional expertise-specific models, without changing source code or committing secrets.

## Decision
Add `data-layer/config/llm_agents.json` as the data-layer LLM agent registry. The backend loads provider chains from this JSON through `DATA_LAYER_LLM_CONFIG` and `DATA_LAYER_LLM_CHAIN`.

Set `local_ollama_lan` as the default provider chain. This mirrors the product-layer LAN Ollama integration and keeps document analysis local by default.

Secrets remain in environment variables. The JSON only names `api_key_env` values and describes provider type, URL, model, timeout, expertise, and data policy.

The JSON also includes `request_examples` for each configured provider so operators and AI colleagues can see exact API payloads and curl calls for Ollama LAN, the local certification expert, DeepSeek, Gemini, and Groq without reading backend source code. DeepSeek is documented as an enterprise alternative through `enterprise_deepseek_existing`, but the provider is disabled until an environment explicitly enables it and supplies `DEEPSEEK_API_KEY`.

## Alternatives considered
- Keep hardcoded DeepSeek, Gemini, and Groq provider order.
- Store API keys directly in JSON.
- Use only local Ollama and remove cloud fallbacks.

## Rationale
Config-as-code lets each environment add its accessible LLM or expertise-specific model while preserving fallback behavior. It also keeps secrets out of Git and makes the classification error actionable by listing configured providers and env vars.

## Impact
Data-layer now uses Ollama LAN by default. It still supports optional certification-expert Ollama, DeepSeek, Gemini, and Groq through explicit configurable chains. Docker Compose mounts `data-layer/config` read-only into the backend container at `/config`. The config doubles as operational documentation for provider-specific request shapes and keeps provider selection external to the lakehouse data-product model.

## Related links
- GitHub issue:
- GitHub PR:
- Related pages:
  - `data-layer/config/llm_agents.json`
  - `data-layer/backend/app/intelligence/llm.py`
  - `data-layer/docker-compose.yml`

## Tags
- product-layer
- data-layer
- governance
- metadata
- access-control
