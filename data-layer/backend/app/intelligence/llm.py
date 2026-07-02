"""
LLM call layer — DeepSeek primary, Gemini secondary, Groq tertiary.
Serialized via async lock. Auto-fallback with retry on 429/5xx.
"""
import asyncio
import logging
import os
import time

import httpx

log = logging.getLogger("paul.llm")

# ── Provider configs ────────────────────────────────────────────────────────

DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

COOLDOWN_SECONDS = 2.0  # DeepSeek has generous limits, less cooldown needed
MAX_RETRIES = 3
RETRY_CODES = (429, 500, 502, 503)

# Track which providers are temporarily down
_backoff_until: dict[str, float] = {}
_llm_lock = asyncio.Lock()


def _get_key(name: str) -> str:
    return os.getenv(name, "")


# ── Provider call functions ─────────────────────────────────────────────────

async def _call_deepseek(prompt: str, api_key: str) -> str:
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 4096,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            DEEPSEEK_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def _call_gemini(prompt: str, api_key: str) -> str:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{GEMINI_URL}?key={api_key}",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]


async def _call_groq(prompt: str, api_key: str) -> str:
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 4096,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            GROQ_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


# ── Retry + orchestration ──────────────────────────────────────────────────

async def _call_with_retry(fn, provider: str, *args) -> str:
    for attempt in range(MAX_RETRIES):
        try:
            return await fn(*args)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in RETRY_CODES and attempt < MAX_RETRIES - 1:
                delay = COOLDOWN_SECONDS * (2 ** attempt)
                log.warning(f"{provider} {e.response.status_code} — retry {attempt + 1}/{MAX_RETRIES} in {delay:.0f}s")
                await asyncio.sleep(delay)
            else:
                raise
    raise RuntimeError("Unreachable")


# Provider chain: try in order, skip providers that recently failed
PROVIDERS = [
    ("DeepSeek", _call_deepseek, "DEEPSEEK_API_KEY"),
    ("Gemini", _call_gemini, "GEMINI_API_KEY"),
    ("Groq", _call_groq, "GROQ_API_KEY"),
]


async def call_llm(prompt: str) -> str:
    """Call LLM providers in priority order with auto-fallback."""
    async with _llm_lock:
        await asyncio.sleep(COOLDOWN_SECONDS)

        last_error = None
        for name, fn, key_env in PROVIDERS:
            api_key = _get_key(key_env)
            if not api_key:
                continue

            # Skip if this provider recently failed
            if time.time() < _backoff_until.get(name, 0):
                log.info(f"{name} in cooldown — skipping")
                continue

            try:
                result = await _call_with_retry(fn, name, prompt, api_key)
                log.info(f"{name} OK")
                return result
            except httpx.HTTPStatusError as e:
                if e.response.status_code in RETRY_CODES:
                    _backoff_until[name] = time.time() + 60
                    log.warning(f"{name} exhausted retries — skipping for 60s")
                    last_error = e
                else:
                    last_error = e

        if last_error:
            raise last_error
        raise ValueError("No API key configured (DEEPSEEK_API_KEY, GEMINI_API_KEY, or GROQ_API_KEY)")
