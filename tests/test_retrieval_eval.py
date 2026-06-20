import unittest
import json
from pathlib import Path

from cogni_life_os.retrieval_eval import FIXTURE_ROOT, run


class RetrievalEvalTests(unittest.TestCase):
    def test_small_retrieval_eval_passes(self):
        result = run([250])
        self.assertTrue(result["passed"])
        self.assertGreaterEqual(result["results"][0]["indexed_notes"], 250)
        heldout = result["results"][0]["heldout"]
        self.assertGreaterEqual(heldout["aggregate"]["precision_at_5"], 0.65)
        self.assertIn("tuning.json", result["results"][0]["dataset_hashes"])

    def test_heldout_queries_do_not_leak_into_source_code(self):
        heldout = json.loads((FIXTURE_ROOT / "heldout.json").read_text(encoding="utf-8"))
        source_files = list((Path(__file__).resolve().parents[1] / "cogni_life_os").glob("*.py"))
        source_text = "\n".join(path.read_text(encoding="utf-8") for path in source_files)
        for item in heldout["queries"]:
            self.assertNotIn(item["query"], source_text)


if __name__ == "__main__":
    unittest.main()
