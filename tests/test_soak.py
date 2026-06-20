import unittest

from cogni_life_os.soak import run


class SoakTests(unittest.TestCase):
    def test_short_soak_has_no_duplicate_side_effects(self):
        result = run(duration_seconds=0.5, operations=50)
        self.assertTrue(result["passed"], result)


if __name__ == "__main__":
    unittest.main()
