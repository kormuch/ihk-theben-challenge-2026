import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx

from app.intelligence import llm


def ollama_provider(**overrides):
    provider = {
        "label": "Ollama LAN default analyst",
        "type": "ollama_generate",
        "enabled": True,
        "base_url": "http://192.168.178.60:11434",
        "endpoint": "/api/generate",
        "model": "gpt-oss:20b",
        "api_key_env": "OLLAMA_API_KEY",
        "api_key_required": False,
        "timeout_seconds": 120,
    }
    provider.update(overrides)
    return provider


class LLMConfigTests(unittest.TestCase):
    def test_ollama_lan_defaults_to_no_proxy_env(self):
        self.assertFalse(llm.provider_trust_env(ollama_provider()))

    def test_cloud_provider_keeps_environment_routing_by_default(self):
        provider = {
            "type": "openai_chat",
            "url": "https://api.deepseek.com/chat/completions",
            "api_key_env": "DEEPSEEK_API_KEY",
            "api_key_required": True,
        }
        self.assertTrue(llm.provider_trust_env(provider))

    def test_required_env_keys_excludes_optional_ollama_key(self):
        chain = [
            ("ollama_lan", ollama_provider()),
            (
                "deepseek",
                {
                    "type": "openai_chat",
                    "api_key_env": "DEEPSEEK_API_KEY",
                    "api_key_required": True,
                },
            ),
        ]

        self.assertEqual(llm.required_env_keys(chain), ["DEEPSEEK_API_KEY"])

    def test_provider_url_formats_ollama_generate_endpoint(self):
        self.assertEqual(
            llm.provider_url(ollama_provider()),
            "http://192.168.178.60:11434/api/generate",
        )


class LLMRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_ollama_http_client_ignores_proxy_environment(self):
        provider = ollama_provider()
        response = Mock()
        response.json.return_value = {"response": "ok"}

        client = AsyncMock()
        client.post.return_value = response

        with patch.object(llm.httpx, "AsyncClient") as async_client:
            async_client.return_value.__aenter__.return_value = client

            result = await llm._call_ollama_generate("classify", provider, "")

        self.assertEqual(result, "ok")
        async_client.assert_called_once_with(timeout=120.0, trust_env=False)
        client.post.assert_awaited_once()

    async def test_optional_ollama_key_is_not_reported_as_required_on_connect_error(self):
        config = {
            "default_chain": "local_ollama_lan",
            "chains": {"local_ollama_lan": ["ollama_lan"]},
            "providers": {"ollama_lan": ollama_provider()},
        }
        request = httpx.Request("POST", "http://192.168.178.60:11434/api/generate")

        async def fail(*args, **kwargs):
            raise httpx.ConnectError("All connection attempts failed", request=request)

        with (
            patch.object(llm, "load_llm_config", return_value=config),
            patch.object(llm, "_call_with_retry", side_effect=fail),
            patch.object(llm, "COOLDOWN_SECONDS", 0),
            patch.dict(llm._backoff_until, {}, clear=True),
        ):
            with self.assertRaises(ValueError) as raised:
                await llm.call_llm("classify")

        message = str(raised.exception)
        self.assertIn("http://192.168.178.60:11434/api/generate", message)
        self.assertIn("network reachability", message)
        self.assertNotIn("OLLAMA_API_KEY", message)


if __name__ == "__main__":
    unittest.main()
