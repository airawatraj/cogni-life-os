import json
import tempfile
import unittest
from pathlib import Path

from cogni_life_os.evidence_manifest import validate_matrix_evidence, write_manifest


class EvidenceManifestTests(unittest.TestCase):
    def test_manifest_and_matrix_consistency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / ".cogni" / "local-candidate-evidence-v5"
            evidence.mkdir(parents=True)
            live = {
                "run_metadata": {},
                "endpoint_discovery": {},
                "model_identity": {},
                "request_configuration": {},
                "contract_findings": {},
                "scenario_count": 1,
                "passed": 1,
                "failed": 0,
                "success_rate": 1.0,
                "latency_metrics": {},
                "results": [
                    {
                        "scenario_id": "final_text",
                        "purpose": "test",
                        "request": {},
                        "response_metadata": {},
                        "normalised_result": {},
                        "expected_behavior": "pass",
                        "actual_behavior": "pass",
                        "status": "pass",
                        "attempts": [],
                        "timeout_state": "not_timed_out",
                        "finish_reason": "stop",
                        "content_presence": "present",
                        "tool_calls": [],
                        "errors": [],
                    }
                ],
            }
            (evidence / "live-model-contract.json").write_text(json.dumps(live), encoding="utf-8")
            matrix = root / "matrix.md"
            matrix.write_text(
                "| Requirement ID | Requirement | Evidence | Status |\n"
                "| --- | --- | --- | --- |\n"
                "| 20 | live | `.cogni/local-candidate-evidence-v5/live-model-contract.json` | PASS |\n",
                encoding="utf-8",
            )
            manifest = write_manifest(evidence)
            result = validate_matrix_evidence(matrix, root)
            self.assertTrue(result["passed"], result["errors"])
            self.assertTrue(manifest["files"])

    def test_matrix_rejects_hidden_live_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / ".cogni" / "local-candidate-evidence-v5"
            evidence.mkdir(parents=True)
            (evidence / "live-model-contract.json").write_text(json.dumps({"scenario_count": 1, "passed": 0, "failed": 1, "results": []}), encoding="utf-8")
            matrix = root / "matrix.md"
            matrix.write_text(
                "| Requirement ID | Requirement | Evidence | Status |\n"
                "| --- | --- | --- | --- |\n"
                "| 20 | live | `.cogni/local-candidate-evidence-v5/live-model-contract.json` | PASS |\n",
                encoding="utf-8",
            )
            result = validate_matrix_evidence(matrix, root)
            self.assertFalse(result["passed"])
