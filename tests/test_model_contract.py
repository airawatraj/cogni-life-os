import json
import unittest

from cogni_life_os.config import settings
from cogni_life_os import model_contract


class ModelContractTests(unittest.TestCase):
    def test_probe_accepts_trimmed_json_and_separates_reasoning(self):
        original = model_contract.chat
        original_discovery = model_contract.discover_endpoint

        def fake_discovery(_settings, timeout=10):
            return {"status": 200, "response": {"data": [{"id": "Cogni-Brain", "root": "fake", "owned_by": "vllm", "max_model_len": 1000}]}}

        def fake_chat(_settings, messages, timeout=None, max_tokens=256, response_format=None, tools=None, tool_choice=None):
            if tools and "search the vault" in messages[-1]["content"]:
                return {"choices": [{"finish_reason": "tool_calls", "message": {"content": None, "tool_calls": [{"type": "function", "function": {"name": "vault_search", "arguments": "{\"query\":\"vehicle renewal\"}"}}]}}]}
            if tools:
                return {"choices": [{"finish_reason": "stop", "message": {"content": "Hello", "tool_calls": []}}]}
            text = messages[-1]["content"]
            if "single token" in text:
                content = "COGNI_TEXT_OK"
            elif "prompt injection" in text.lower() or "ignore prior" in text.lower():
                content = '{"decision":"quarantine","terminal_state":"quarantined","side_effects":[],"unauthorised_tool_calls":[]}'
            elif "publish it externally" in text:
                content = '{"decision":"refuse","external_action_allowed":false,"terminal_state":"refused","side_effects":[]}'
            elif "dermatologist" in text:
                content = '{"domain":"personal_health","action_scope":"personal","cross_domain_leakage":false}'
            elif "Atlas client" in text:
                content = '{"domain":"confidential_work","action_scope":"work","cross_domain_leakage":false}'
            elif "registration invoice" in text:
                content = '{"domains":["administrative","financial"],"action_scope":"personal_admin","cross_domain_leakage":false}'
            else:
                content = '{"ok":true,"storage":"Markdown"}'
            return {"choices": [{"finish_reason": "stop", "message": {"content": content, "reasoning": "hidden"}}]}

        try:
            model_contract.chat = fake_chat
            model_contract.discover_endpoint = fake_discovery
            result = model_contract.run_probes(settings())
        finally:
            model_contract.chat = original
            model_contract.discover_endpoint = original_discovery

        self.assertEqual(model_contract.validate_evidence_schema(result), [])
        self.assertEqual(result["scenario_count"], len(result["results"]))
        self.assertTrue(any(item["normalised_result"]["reasoning_present"] for item in result["results"]))
        self.assertGreater(result["failed"], 0)

    def test_live_evidence_schema_rejects_substituted_evaluation_summary(self):
        bad = {"passed": 6, "results": [{"test_name": "live Cogni-Brain contract"}]}
        errors = model_contract.validate_evidence_schema(bad)
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
