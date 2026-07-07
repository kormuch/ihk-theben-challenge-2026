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
            "trust_env": False,
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


def required_env_keys(chain: list[tuple[str, dict[str, Any]]]) -> list[str]:
    keys = [
        env_key(provider)
        for _, provider in chain
        if provider.get("api_key_required", False) and env_key(provider)
    ]
    return sorted(set(keys))


def provider_trust_env(provider: dict[str, Any]) -> bool:
    """Whether httpx should honor proxy-related environment variables."""
    if "trust_env" in provider:
        return bool(provider.get("trust_env"))
    return provider.get("type") != "ollama_generate"


def provider_url(provider: dict[str, Any]) -> str:
    if provider.get("_resolved_url"):
        return str(provider["_resolved_url"])
    provider_type = provider.get("type")
    if provider_type == "ollama_generate":
        base_url = str(provider.get("base_url") or "").rstrip("/")
        endpoint = str(provider.get("endpoint") or "/api/generate")
        return f"{base_url}{endpoint if endpoint.startswith('/') else '/' + endpoint}"
    return str(provider.get("url") or "")


def _append_endpoint(base_url: str, endpoint: str) -> str:
    clean_base = str(base_url or "").rstrip("/")
    if not clean_base:
        return ""
    clean_endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    return f"{clean_base}{clean_endpoint}"


def provider_urls(provider: dict[str, Any]) -> list[str]:
    """Return request URL candidates for one provider in failover order."""
    if provider.get("type") != "ollama_generate":
        url = provider_url(provider)
        return [url] if url else []

    endpoint = str(provider.get("endpoint") or "/api/generate")
    base_urls: list[str] = []
    override = os.getenv("DATA_LAYER_OLLAMA_BASE_URL") or os.getenv("OLLAMA_BASE_URL")
    if override:
        base_urls.append(override)

    configured_base_urls = provider.get("base_urls")
    if isinstance(configured_base_urls, list):
        base_urls.extend(str(item) for item in configured_base_urls if str(item).strip())

    fallback_base_urls = provider.get("fallback_base_urls")
    if isinstance(fallback_base_urls, list):
        base_urls.extend(str(item) for item in fallback_base_urls if str(item).strip())

    if provider.get("base_url"):
        base_urls.append(str(provider["base_url"]))

    urls: list[str] = []
    seen: set[str] = set()
    for base_url in base_urls:
        url = _append_endpoint(base_url, endpoint)
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def exception_summary(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        body = response.text.strip().replace("\n", " ")[:400]
        suffix = f": {body}" if body else ""
        return f"HTTP {response.status_code}{suffix}"
    if isinstance(exc, httpx.RequestError):
        return f"{exc.__class__.__name__}: {exc}"
    return str(exc)


async def _call_openai_chat(prompt: str, provider: dict[str, Any], api_key: str) -> str:
    payload = {
        "model": provider["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": provider.get("temperature", 0.1),
        "max_tokens": provider.get("max_tokens", 4096),
    }
    async with httpx.AsyncClient(
        timeout=float(provider.get("timeout_seconds", 60)),
        trust_env=provider_trust_env(provider),
    ) as client:
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
    async with httpx.AsyncClient(
        timeout=float(provider.get("timeout_seconds", 60)),
        trust_env=provider_trust_env(provider),
    ) as client:
        response = await client.post(
            f"{provider['url']}?key={api_key}",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]


async def _call_ollama_generate(prompt: str, provider: dict[str, Any], api_key: str) -> str:
    url = provider_url(provider)
    if not url.startswith(("http://", "https://")):
        raise ValueError("Ollama provider requires base_url with http:// or https://")
    payload = {
        "model": provider["model"],
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": provider.get("temperature", 0.1)},
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with httpx.AsyncClient(
        timeout=float(provider.get("timeout_seconds", 120)),
        trust_env=provider_trust_env(provider),
    ) as client:
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
    urls = provider_urls(provider)
    if not urls:
        raise ValueError(f"{name} has no configured request URL")
    last_exc: Exception | None = None
    saw_retryable = False
    for attempt in range(MAX_RETRIES):
        for index, url in enumerate(urls, start=1):
            resolved_provider = {**provider, "_resolved_url": url}
            try:
                return await _call_provider(prompt, resolved_provider, api_key)
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                retryable = isinstance(exc, httpx.RequestError) or exc.response.status_code in RETRY_CODES
                last_exc = exc
                saw_retryable = saw_retryable or retryable
                log.warning(
                    "%s at %s %s - failed candidate %s/%s on attempt %s/%s",
                    name,
                    url,
                    exception_summary(exc),
                    index,
                    len(urls),
                    attempt + 1,
                    MAX_RETRIES,
                )
        if saw_retryable and attempt < MAX_RETRIES - 1:
            delay = COOLDOWN_SECONDS * (2**attempt)
            log.warning("%s exhausted %d candidate URL(s) - retry %s/%s in %.0fs", name, len(urls), attempt + 1, MAX_RETRIES, delay)
            await asyncio.sleep(delay)
        elif last_exc:
            raise last_exc
    raise RuntimeError("Unreachable")


def get_active_config() -> dict[str, Any]:
    """Return a safe summary of the active LLM configuration (no secrets)."""
    config = load_llm_config()
    chain = provider_chain(config)
    chain_name = os.getenv("DATA_LAYER_LLM_CHAIN") or str(config.get("default_chain") or "analysis_default")
    providers_summary = []
    for pid, prov in chain:
        providers_summary.append({
            "id": pid,
            "label": provider_label(pid, prov),
            "type": prov.get("type"),
            "urls": provider_urls(prov),
            "model": prov.get("model"),
            "temperature": prov.get("temperature"),
            "max_tokens": prov.get("max_tokens"),
            "timeout_seconds": prov.get("timeout_seconds"),
            "api_key_required": prov.get("api_key_required", False),
            "api_key_configured": bool(get_api_key(prov)),
        })
    return {
        "chain": chain_name,
        "providers": providers_summary,
        "cooldown_seconds": COOLDOWN_SECONDS,
        "max_retries": MAX_RETRIES,
    }


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
                urls = ", ".join(provider_urls(provider)) or "unconfigured URL"
                last_error = f"{name} at {urls}: {exception_summary(exc)}"
            except ValueError as exc:
                last_error = f"{name}: {exc}"

        if last_error:
            keys = ", ".join(required_env_keys(chain))
            key_hint = f" Required env vars: {keys}." if keys else ""
            raise ValueError(
                f"No configured LLM provider is usable. Last provider error: {last_error}. "
                f"Configure data-layer/config/llm_agents.json or check provider network reachability.{key_hint}"
            )

        keys = ", ".join(required_env_keys(chain))
        missing = "; skipped missing keys: " + ", ".join(skipped_missing_key) if skipped_missing_key else ""
        key_hint = f" or set env vars: {keys}" if keys else ""
        raise ValueError(
            f"No configured LLM provider is usable. Configure data-layer/config/llm_agents.json{key_hint}{missing}"
        )
