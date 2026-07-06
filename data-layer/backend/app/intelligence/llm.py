"""
LLM call layer for data-layer document analysis.

Provider order and agent definitions are loaded from config/llm_agents.json.
Secrets stay in environment variables; config only names the env var to read.
"""
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("paul.llm")

DEFAULT_CONFIG = {
    "default_chain": "local_ollama_lan",
    "chains": {
        "analysis_default": ["ollama_lan"],
        "local_ollama_lan": ["ollama_lan"],
        "local_only": ["ollama_lan"],
        "enterprise_deepseek_existing": ["deepseek"],
    },
    "providers": {
        "ollama_lan": {
            "label": "Ollama LAN default analyst",
            "type": "ollama_generate",
            "enabled": True,
            "base_url": "http://192.168.178.60:11434",
            "endpoint": "/api/generate",
            "model": "gpt-oss:20b",
            "api_key_env": "OLLAMA_API_KEY",
            "api_key_required": False,
            "temperature": 0.1,
            "max_tokens": 4096,
            "timeout_seconds": 120,
        },
        "deepseek": {
            "label": "DeepSeek existing enterprise alternative",
            "type": "openai_chat",
            "enabled": False,
            "url": "https://api.deepseek.com/chat/completions",
            "model": "deepseek-chat",
            "api_key_env": "DEEPSEEK_API_KEY",
            "api_key_required": True,
            "temperature": 0.1,
            "max_tokens": 4096,
            "timeout_seconds": 60,
        },
    },
}

COOLDOWN_SECONDS = float(os.getenv("LLM_COOLDOWN_SECONDS", "2.0"))
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
RETRY_CODES = (429, 500, 502, 503)

_backoff_until: dict[str, float] = {}
_llm_lock = asyncio.Lock()


def config_path() -> Path:
    configured = os.getenv("DATA_LAYER_LLM_CONFIG", "").strip()
    if configured:
        return Path(configured)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "config" / "llm_agents.json"
        if candidate.exists():
            return candidate
    return here.parents[3] / "config" / "llm_agents.json"


def load_llm_config() -> dict[str, Any]:
    path = config_path()
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        log.warning("LLM config not found at %s; using built-in fallback", path)
        payload = DEFAULT_CONFIG
    if not isinstance(payload, dict):
        raise ValueError(f"LLM config must be a JSON object: {path}")
    return payload


def provider_chain(config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    chain_name = os.getenv("DATA_LAYER_LLM_CHAIN") or str(config.get("default_chain") or "analysis_default")
    chains = config.get("chains") if isinstance(config.get("chains"), dict) else {}
    provider_ids = chains.get(chain_name) or chains.get("analysis_default") or []
    providers = config.get("providers") if isinstance(config.get("providers"), dict) else {}
    chain: list[tuple[str, dict[str, Any]]] = []
    for provider_id in provider_ids:
        provider = providers.get(provider_id)
        if isinstance(provider, dict) and provider.get("enabled", True):
            chain.append((str(provider_id), provider))
    return chain


def provider_label(provider_id: str, provider: dict[str, Any]) -> str:
    return str(provider.get("label") or provider_id)


def env_key(provider: dict[str, Any]) -> str:
    return str(provider.get("api_key_env") or "").strip()


def get_api_key(provider: dict[str, Any]) -> str:
    key_name = env_key(provider)
    return os.getenv(key_name, "") if key_name else ""


def configured_env_keys(chain: list[tuple[str, dict[str, Any]]]) -> list[str]:
    keys = [env_key(provider) for _, provider in chain if env_key(provider)]
    return sorted(set(keys))


async def _call_openai_chat(prompt: str, provider: dict[str, Any], api_key: str) -> str:
    payload = {
        "model": provider["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": provider.get("temperature", 0.1),
        "max_tokens": provider.get("max_tokens", 4096),
    }
    async with httpx.AsyncClient(timeout=float(provider.get("timeout_seconds", 60))) as client:
        response = await client.post(
            provider["url"],
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


async def _call_gemini(prompt: str, provider: dict[str, Any], api_key: str) -> str:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": provider.get("temperature", 0.1),
            "maxOutputTokens": provider.get("max_tokens", 4096),
        },
    }
    async with httpx.AsyncClient(timeout=float(provider.get("timeout_seconds", 60))) as client:
        response = await client.post(
            f"{provider['url']}?key={api_key}",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]


async def _call_ollama_generate(prompt: str, provider: dict[str, Any], api_key: str) -> str:
    base_url = str(provider.get("base_url") or "").rstrip("/")
    endpoint = str(provider.get("endpoint") or "/api/generate")
    url = f"{base_url}{endpoint if endpoint.startswith('/') else '/' + endpoint}"
    payload = {
        "model": provider["model"],
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": provider.get("temperature", 0.1)},
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with httpx.AsyncClient(timeout=float(provider.get("timeout_seconds", 120))) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json().get("response", "")


async def _call_provider(prompt: str, provider: dict[str, Any], api_key: str) -> str:
    provider_type = provider.get("type")
    if provider_type == "openai_chat":
        return await _call_openai_chat(prompt, provider, api_key)
    if provider_type == "gemini_generate":
        return await _call_gemini(prompt, provider, api_key)
    if provider_type == "ollama_generate":
        return await _call_ollama_generate(prompt, provider, api_key)
    raise ValueError(f"Unsupported LLM provider type: {provider_type}")


async def _call_with_retry(prompt: str, provider_id: str, provider: dict[str, Any], api_key: str) -> str:
    name = provider_label(provider_id, provider)
    for attempt in range(MAX_RETRIES):
        try:
            return await _call_provider(prompt, provider, api_key)
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            retryable = isinstance(exc, httpx.RequestError) or exc.response.status_code in RETRY_CODES
            if retryable and attempt < MAX_RETRIES - 1:
                delay = COOLDOWN_SECONDS * (2**attempt)
                reason = getattr(getattr(exc, "response", None), "status_code", exc.__class__.__name__)
                log.warning("%s %s - retry %s/%s in %.0fs", name, reason, attempt + 1, MAX_RETRIES, delay)
                await asyncio.sleep(delay)
            else:
                raise
    raise RuntimeError("Unreachable")


async def call_llm(prompt: str) -> str:
    """Call configured LLM providers in priority order with auto-fallback."""
    async with _llm_lock:
        await asyncio.sleep(COOLDOWN_SECONDS)

        config = load_llm_config()
        chain = provider_chain(config)
        last_error = None
        skipped_missing_key: list[str] = []

        for provider_id, provider in chain:
            name = provider_label(provider_id, provider)
            api_key = get_api_key(provider)
            if provider.get("api_key_required", False) and not api_key:
                skipped_missing_key.append(f"{name} ({env_key(provider)})")
                continue

            if time.time() < _backoff_until.get(provider_id, 0):
                log.info("%s in cooldown - skipping", name)
                continue

            try:
                result = await _call_with_retry(prompt, provider_id, provider, api_key)
                log.info("%s OK", name)
                return result
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                retryable = isinstance(exc, httpx.RequestError) or exc.response.status_code in RETRY_CODES
                if retryable:
                    _backoff_until[provider_id] = time.time() + 60
                    log.warning("%s exhausted retries - skipping for 60s", name)
                last_error = exc

        if last_error:
            keys = ", ".join(configured_env_keys(chain)) or "no api_key_env values configured"
            raise ValueError(
                f"No configured LLM provider is usable. Last provider error: {last_error}. "
                f"Configure data-layer/config/llm_agents.json or set env vars: {keys}"
            ) from last_error

        keys = ", ".join(configured_env_keys(chain)) or "no api_key_env values configured"
        missing = "; skipped missing keys: " + ", ".join(skipped_missing_key) if skipped_missing_key else ""
        raise ValueError(
            f"No configured LLM provider is usable. Configure data-layer/config/llm_agents.json or set env vars: {keys}{missing}"
        )
