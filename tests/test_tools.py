import tempfile
import unittest
from pathlib import Path

from cogni_life_os.indexer import Index
from cogni_life_os.durable_agent import DurableAgentStore
from cogni_life_os.tools import registry
from cogni_life_os.vault import Vault


class ToolTests(unittest.TestCase):
    def test_registry_has_no_tool_not_ready_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            tools = registry(vault, Index(Path(tmp) / "idx.sqlite3"))
            for name, spec in tools.items():
                self.assertNotIn("TOOL_NOT_READY", repr(spec.handler))

    def test_proposal_pipeline_applies_allowed_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            tools = registry(vault, Index(Path(tmp) / "idx.sqlite3"))
            proposal = {
                "action": "create",
                "path": "30-concepts/test.md",
                "content": "---\nid: concept-test\ntype: concept\n---\n\n# Test\n",
                "evidence": ["source-test"],
                "sensitivity": "low",
                "confidence": 0.9,
                "domain": "general_knowledge",
            }
            vault.write_note("10-sources/text/source-test.md", {"id": "source-test", "type": "raw_source"}, "# Source\n", expected_hash=None)
            plan = tools["write_plan_creation"].run({"proposal": proposal})
            self.assertEqual(plan["status"], "ready")
            applied = tools["controlled_write_application"].run({"plan": plan})
            self.assertEqual(applied["status"], "applied")
            self.assertTrue((vault.root / "30-concepts/test.md").exists())

    def test_sensitive_proposal_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            tools = registry(vault, Index(Path(tmp) / "idx.sqlite3"))
            vault.write_note("10-sources/text/s.md", {"id": "s", "type": "raw_source"}, "# Source\n", expected_hash=None)
            proposal = {"action": "create", "path": "30-concepts/x.md", "content": "x", "evidence": ["s"], "sensitivity": "medical", "confidence": 0.9, "domain": "health"}
            validation = tools["proposal_validation"].run({"proposal": proposal})
            self.assertFalse(validation["valid"])

    def test_proposal_requires_existing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            tools = registry(vault, Index(Path(tmp) / "idx.sqlite3"))
            proposal = {"action": "create", "path": "30-concepts/x.md", "content": "x", "evidence": ["missing"], "sensitivity": "low", "confidence": 0.9, "domain": "general_knowledge"}
            validation = tools["proposal_validation"].run({"proposal": proposal})
            self.assertFalse(validation["valid"])
            self.assertIn("evidence", " ".join(validation["errors"]))

    def test_multi_file_write_plan_rolls_back_on_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            vault.write_note("10-sources/text/src.md", {"id": "src", "type": "raw_source"}, "# Source\n", expected_hash=None)
            vault.write_note("30-concepts/existing.md", {"id": "existing", "type": "concept"}, "# Existing\n", expected_hash=None)
            tools = registry(vault, Index(Path(tmp) / "idx.sqlite3"))
            proposal = {
                "action": "replace",
                "files": [
                    {"path": "30-concepts/new.md", "content": "# New\n"},
                    {"path": "30-concepts/existing.md", "content": "# Bad\n", "expected_hash": "wrong"},
                ],
                "evidence": ["src"],
                "sensitivity": "low",
                "confidence": 0.9,
                "domain": "general_knowledge",
            }
            plan = tools["write_plan_creation"].run({"proposal": proposal})
            self.assertEqual(plan["status"], "rejected")

    def test_retry_updates_durable_task_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            DurableAgentStore(vault).create("task-retry", "source-retry")
            tools = registry(vault, Index(Path(tmp) / "idx.sqlite3"))
            result = tools["retry"].run({"task_id": "task-retry", "reason": "endpoint timeout"})
            self.assertEqual(result["status"], "retry_scheduled")
            status = tools["task_status"].run({"task_id": "task-retry"})
            self.assertEqual(status["state"]["retry_state"]["retries"], 1)

    def test_vault_qa_is_citation_grounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            vault.write_note("30-concepts/ground.md", {"id": "ground", "type": "concept"}, "# Ground\n\ninsurance renewal evidence", expected_hash=None)
            index = Index(Path(tmp) / "idx.sqlite3")
            index.rebuild(vault)
            answer = registry(vault, index)["vault_question_answering"].run({"question": "insurance renewal"})
            self.assertEqual(answer["status"], "answered_with_citations")
            self.assertTrue(answer["citations"])


if __name__ == "__main__":
    unittest.main()
