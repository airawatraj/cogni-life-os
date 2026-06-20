import os
import tempfile
import threading
import unittest
from pathlib import Path

from cogni_life_os.indexer import Index
from cogni_life_os.ingest import capture_text
from cogni_life_os.vault import Vault


def fd_count() -> int:
    return len(os.listdir("/dev/fd"))


class ResourceCleanupTests(unittest.TestCase):
    def test_index_search_and_rebuild_do_not_leak_file_descriptors(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            capture_text(vault, "resource cleanup query")
            index = Index(Path(tmp) / "index.sqlite3")
            before = fd_count()
            for _ in range(50):
                index.rebuild(vault)
                index.search("resource")
                index.health()
            after = fd_count()
            self.assertLessEqual(after - before, 2)
            self.assertEqual(Index.active_connections, 0)

    def test_index_error_paths_do_not_leak_connections(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = Index(Path(tmp) / "index.sqlite3")
            before = fd_count()
            for _ in range(20):
                with self.assertRaises(Exception):
                    index.search('"unterminated')
            after = fd_count()
            self.assertLessEqual(after - before, 2)
            self.assertEqual(Index.active_connections, 0)

    def test_incremental_update_and_concurrent_readers_do_not_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Vault(Path(tmp) / "vault")
            vault.init()
            capture_text(vault, "resource cleanup concurrent")
            index = Index(Path(tmp) / "index.sqlite3")
            index.rebuild(vault)
            before = fd_count()
            errors = []

            def reader():
                try:
                    for _ in range(50):
                        index.search("resource")
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=reader) for _ in range(6)]
            for thread in threads:
                thread.start()
            for i in range(25):
                vault.write_note(f"30-concepts/inc-{i}.md", {"id": f"inc-{i}", "type": "concept"}, f"# Incremental {i}\nresource", expected_hash=None)
                index.update_note(vault, f"30-concepts/inc-{i}.md")
            for thread in threads:
                thread.join()

            after = fd_count()
            self.assertEqual(errors, [])
            self.assertLessEqual(after - before, 2)
            self.assertEqual(Index.active_connections, 0)


if __name__ == "__main__":
    unittest.main()
