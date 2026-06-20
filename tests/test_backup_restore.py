import tempfile
import unittest
from pathlib import Path

from cogni_life_os.backup import create_backup, file_hashes, restore_backup
from cogni_life_os.indexer import Index
from cogni_life_os.ingest import capture_binary, capture_text
from cogni_life_os.vault import Vault


class BackupRestoreTests(unittest.TestCase):
    def test_complete_restore_rehearsal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = Vault(root / "vault")
            vault.init()
            capture_text(vault, "Restore rehearsal text")
            capture_binary(vault, b"%PDF-1.4\nBT (Restore PDF) Tj ET\n%%EOF", "restore.pdf")
            Index(root / "index.sqlite3").rebuild(vault)
            source_hashes = file_hashes(vault.root)
            manifest = create_backup(vault, root / "backups")
            manifest_path = Path(manifest["archive"]).with_suffix("").with_suffix(".json")
            restored = restore_backup(manifest_path, root / "empty-restore", root / "restored-index.sqlite3")
            self.assertEqual(restored["integrity"]["status"], "pass")
            self.assertEqual(source_hashes, restored["hashes"])
            self.assertGreater(restored["index_rebuilt_count"], 0)


if __name__ == "__main__":
    unittest.main()
