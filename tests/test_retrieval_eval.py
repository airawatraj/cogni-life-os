import unittest

from cogni_life_os.retrieval_eval import run


class RetrievalEvalTests(unittest.TestCase):
    def test_small_retrieval_eval_passes(self):
        result = run([250])
        self.assertTrue(result["passed"])
        self.assertEqual(result["results"][0]["indexed_notes"], 252)


if __name__ == "__main__":
    unittest.main()
