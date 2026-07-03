# QR-2026-07-03-001 - Data-layer LLM config validation

## Purpose
Validate that data-layer document classification uses LAN Ollama by default and can be reconfigured through JSON provider chains instead of failing only on missing DeepSeek, Gemini, or Groq API keys.

## Scope
Validated `config/llm_agents.json`, provider-specific request examples, backend LLM provider-chain loading, Python syntax, default LAN Ollama chain selection without network calls, and Docker Compose config rendering.

## Results
- Passed: `python3 -m json.tool config/llm_agents.json`.
- Passed: `PYTHONPYCACHEPREFIX=/private/tmp/thebenpaul-pycache python3 -m py_compile backend/app/intelligence/llm.py backend/app/intelligence/classifier.py`.
- Passed: loader check with no chain override selected default chain `local_ollama_lan` and provider `ollama_lan`.
- Passed: `docker compose config` shows `/config/llm_agents.json` mounted, `DATA_LAYER_LLM_CONFIG=/config/llm_agents.json`, and `DATA_LAYER_LLM_CHAIN=local_ollama_lan`.
- Passed: `request_examples` now includes API call shapes for Ollama LAN, certification expert Ollama, DeepSeek, Gemini, and Groq.
- Failed: none.
- Skipped: real LLM network calls and model output quality checks.

## Observations
The backend now defaults to LAN Ollama and preserves external providers as explicit enterprise alternatives. Network failures from one configured provider no longer block fallback providers automatically when an approved fallback chain is selected.

## Action items
- Add real provider secrets through deployment secrets or `.env` outside Git.
- In each environment, choose `DATA_LAYER_LLM_CHAIN` according to allowed data movement and model availability.
- Add an optional live LLM health check later that does not break offline CI.

## Related links
- GitHub workflow:
- Logs:
- Release:
