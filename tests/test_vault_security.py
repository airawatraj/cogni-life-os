import os
import tempfile
import unittest
from pathlib import Path

from cogni_life_os.path_safety import PathSafetyError, safe_join
from cogni_life_os.vault import Vault


class VaultSecurityTests(unittest.TestCase):
    def test_absolute_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PathSafetyError):
                safe_join(Path(tmp) / "vault", "/tmp/evil.md")

    def test_prefix_collision_does_not_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            sibling = Path(tmp) / "vault-other"
            sibling.mkdir()
            with self.assertRaises(PathSafetyError):
                safe_join(root, "../vault-other/x.md")

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            outside = Path(tmp) / "outside"
            root.mkdir()
            outside.mkdir()
            os.symlink(outside, root / "link")
            with self.assertRaises(PathSafetyError):
                safe_join(root, "link/escape.md")

    def test_bounded_write_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            vault.max_write_bytes = 4
            with self.assertRaises(ValueError):
                vault.atomic_write("x.md", b"12345", expected_hash=None)

    def test_protected_audit_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            with self.assertRaises(PermissionError):
                vault.atomic_write("00-system/audit/audit.jsonl", b"tamper", expected_hash=None, allow_existing=True)

    def test_rollback_restores_backup_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            vault.atomic_write("note.md", b"one", expected_hash=None)
            vault.atomic_write("backup/note.md", b"one", expected_hash=None)
            vault.atomic_write("note.md", b"two", expected_hash=vault.hash_file("note.md"))
            vault.rollback("note.md", "backup/note.md")
            self.assertEqual(vault.read_bytes("note.md"), b"one")


if __name__ == "__main__":
    unittest.main()
