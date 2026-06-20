import json
import unittest

from cogni_life_os.config import settings
from cogni_life_os import model_contract


class ModelContractTests(unittest.TestCase):
    def test_probe_accepts_trimmed_json_and_separates_reasoning(self):
        original = model_contract.chat

        def fake_chat(_settings, messages, timeout=None, max_tokens=256, response_format=None):
            content = "\n\n{\"ok\": true, \"tool\": null}" if "JSON" in messages[-1]["content"] else "\n\nCOGNI_TEXT_OK"
            return {"choices": [{"message": {"content": content, "reasoning": "hidden"}}]}

        try:
            model_contract.chat = fake_chat
            result = model_contract.run_probes(settings())
        finally:
            model_contract.chat = original

        self.assertTrue(all(item["status"] == "pass" for item in result["results"][:2]))
        self.assertTrue(result["results"][0]["issues"])


if __name__ == "__main__":
    unittest.main()
