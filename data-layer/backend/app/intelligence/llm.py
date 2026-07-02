"""
LLM call layer — Gemini primary, Groq fallback.
Serialized via async lock to respect free-tier rate limits.
"""
import asyncio
import logging
import os
import time

import httpx

log = logging.getLogger("paul.llm")

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

COOLDOWN_SECONDS = 4.0
MAX_RETRIES = 3
RETRY_CODES = (429, 500, 502, 503)

# After Gemini fails, skip it for this many seconds to avoid wasting time on retries.
_gemini_backoff_until = 0.0

# Global lock: only one LLM call at a time.
_llm_lock = asyncio.Lock()


def _get_gemini_key() -> str:
    return os.getenv("GEMINI_API_KEY", "")


def _get_groq_key() -> str:
    return os.getenv("GROQ_API_KEY", "")


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


async def _call_with_retry(fn, provider: str, *args) -> str:
    """Call an LLM provider with exponential backoff on rate-limit/server errors."""
    for attempt in range(MAX_RETRIES):
        try:
            return await fn(*args)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in RETRY_CODES and attempt < MAX_RETRIES - 1:
                delay = COOLDOWN_SECONDS * (2 ** attempt)  # 4s, 8s
                log.warning(f"{provider} {e.response.status_code} — retry {attempt + 1}/{MAX_RETRIES} in {delay:.0f}s")
                await asyncio.sleep(delay)
            else:
                raise
    raise RuntimeError("Unreachable")


async def call_llm(prompt: str) -> str:
    """Call Gemini (preferred) or Groq. Serialized via lock to respect rate limits."""
    global _gemini_backoff_until

    async with _llm_lock:
        await asyncio.sleep(COOLDOWN_SECONDS)

        gemini_key = _get_gemini_key()
        groq_key = _get_groq_key()

        # Try Gemini unless it recently failed
        if gemini_key and time.time() >= _gemini_backoff_until:
            try:
                result = await _call_with_retry(_call_gemini, "Gemini", prompt, gemini_key)
                return result
            except httpx.HTTPStatusError as e:
                if e.response.status_code in RETRY_CODES and groq_key:
                    # Skip Gemini for 60s so subsequent calls go straight to Groq
                    _gemini_backoff_until = time.time() + 60
                    log.warning("Gemini exhausted retries — using Groq for next 60s")
                    return await _call_with_retry(_call_groq, "Groq", prompt, groq_key)
                raise
        elif gemini_key and groq_key:
            log.info("Gemini in cooldown — using Groq directly")

        if groq_key:
            return await _call_with_retry(_call_groq, "Groq", prompt, groq_key)

        if gemini_key:
            # Groq not available, must try Gemini even if in cooldown
            return await _call_with_retry(_call_gemini, "Gemini", prompt, gemini_key)

        raise ValueError("No API key configured (GEMINI_API_KEY or GROQ_API_KEY)")
