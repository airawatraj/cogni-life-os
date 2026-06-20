import tempfile
import unittest
from pathlib import Path

from cogni_life_os.durable_agent import DurableAgentStore, deterministic_operation_id
from cogni_life_os.vault import Vault


class DurableAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Vault(Path(self.tmp.name) / "vault")
        self.vault.init()
        self.store = DurableAgentStore(self.vault)

    def tearDown(self):
        self.tmp.cleanup()

    def test_operation_id_ignores_model_tool_call_id(self):
        a = deterministic_operation_id("task-1", "source-1", "note_read", {"path": "x.md"}, "read")
        b = deterministic_operation_id("task-1", "source-1", "note_read", {"path": "x.md"}, "read")
        self.assertEqual(a, b)

    def test_persists_model_request_without_credentials(self):
        state = self.store.create("task-a", "source-a")
        state = self.store.persist_model_request(state, {"api_key": "secret", "messages": [{"content": "x"}]})
        loaded = self.store.load("task-a")
        self.assertEqual(loaded.phase, "model_request_pending")
        self.assertEqual(loaded.pending_model_request["api_key"], "[REDACTED]")

    def test_recovery_from_restart_before_tool_execution(self):
        state = self.store.create("task-b", "source-b")
        state = self.store.persist_tool_intent(state, "note_read", {"path": "x.md"}, "read", {"x.md": None})
        recovered = self.store.recover("task-b", "worker-1")
        self.assertEqual(recovered.operation_state, "ready_to_execute_after_restart")

    def test_recovery_after_verified_side_effect_completes_idempotently(self):
        state = self.store.create("task-c", "source-c")
        state = self.store.mark_side_effect(state, {"path": "x.md", "sha256": "abc"})
        recovered = self.store.recover("task-c", "worker-1")
        final = self.store.complete(recovered)
        again = self.store.complete(final)
        self.assertEqual(again.final_status, "completed")
        self.assertEqual(len(again.completed_side_effects), 1)

    def test_stale_lease_can_be_reacquired_but_active_lease_blocks(self):
        self.store.create("task-d", "source-d")
        self.store.acquire_lease("task-d", "worker-1", seconds=60)
        with self.assertRaises(RuntimeError):
            self.store.acquire_lease("task-d", "worker-2", seconds=60)

    def test_malformed_record_quarantines(self):
        (self.vault.root / "00-system/tasks/bad.md").write_text("not markdown state", encoding="utf-8")
        state = self.store.recover("bad", "worker")
        self.assertEqual(state.phase, "quarantined")


if __name__ == "__main__":
    unittest.main()
