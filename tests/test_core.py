import tempfile
import unittest
from pathlib import Path

from cogni_life_os.config import Settings
from cogni_life_os.indexer import Index
from cogni_life_os.ingest import capture_text
from cogni_life_os.integrity import scan
from cogni_life_os.path_safety import PathSafetyError, safe_join
from cogni_life_os.vault import Vault


class CoreTests(unittest.TestCase):
    def test_capture_is_idempotent_and_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            first = capture_text(vault, "Pay registration by Friday")
            second = capture_text(vault, "Pay registration by Friday")
            self.assertEqual(first.source_id, second.source_id)
            self.assertTrue(second.duplicate)
            self.assertTrue((vault.root / first.source_path).exists())
            self.assertTrue((vault.root / first.task_path).exists())

    def test_path_escape_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PathSafetyError):
                safe_join(Path(tmp), "../outside.md")

    def test_conflict_created_on_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            vault.atomic_write("x.md", b"one", expected_hash=None)
            result = vault.atomic_write("x.md", b"two", expected_hash="wrong")
            self.assertIsNotNone(result.conflict_path)
            self.assertEqual((vault.root / "x.md").read_bytes(), b"one")

    def test_index_and_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            capture_text(vault, "Ancient and modern knowledge comparison")
            index = Index(Path(tmp) / "index.sqlite3")
            self.assertGreater(index.rebuild(vault), 0)
            self.assertTrue(index.search("ancient"))
            self.assertEqual(scan(vault)["status"], "pass")

    def test_deleting_index_loses_no_authoritative_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            capture_text(vault, "Disposable index reconstruction evidence")
            db = Path(tmp) / "index.sqlite3"
            index = Index(db)
            index.rebuild(vault)
            before = index.search("reconstruction")
            db.unlink()
            rebuilt = Index(db)
            rebuilt.rebuild(vault)
            after = rebuilt.search("reconstruction")
            self.assertEqual(before, after)
            self.assertEqual(scan(vault)["status"], "pass")


if __name__ == "__main__":
    unittest.main()
