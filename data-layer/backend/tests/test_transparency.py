import json
import importlib.util
import unittest
from unittest.mock import patch

from app.api import transparency


class TransparencyEndpointTests(unittest.TestCase):
    def test_transparency_endpoint_uses_editable_prompt_config(self):
        prompt_config = {
            "document_types": ["Datasheet", "Certificate"],
            "classifier_prompt": "Types:\n{types}\nContent:\n{content}",
            "extractor_base_template": "Extract {doc_type}: {specific_instructions}\n{content}",
            "extractor_prompts": {"Datasheet": "Extract electrical attributes."},
            "generic_extractor_instructions": "Extract any product data.",
        }

        with (
            patch.object(transparency, "load_prompts", return_value=prompt_config),
            patch.object(transparency, "get_active_config", return_value={"chain": "local_ollama_lan", "providers": []}),
        ):
            response = transparency.get_prompts()

        payload = json.loads(response.body)
        self.assertEqual(payload["document_types"], ["Datasheet", "Certificate"])
        self.assertIn("- Datasheet", payload["prompts"]["classifier"])
        self.assertIn("<document content>", payload["prompts"]["classifier"])
        self.assertEqual(payload["prompts"]["extractor_per_type"], {"Datasheet": "Extract electrical attributes."})
        self.assertEqual(payload["llm"]["chain"], "local_ollama_lan")

    def test_main_imports_with_transparency_router(self):
        if importlib.util.find_spec("sqlalchemy") is None:
            self.skipTest("sqlalchemy is not installed in the lightweight local test environment")

        from app import main

        routes = {route.path for route in main.app.routes}
        self.assertIn("/api/v1/analyze/prompts", routes)


if __name__ == "__main__":
    unittest.main()
