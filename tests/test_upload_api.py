import base64
import tempfile
import unittest
from pathlib import Path

from cogni_life_os.config import Settings
from cogni_life_os.indexer import Index
from cogni_life_os.server import handle_upload
from cogni_life_os.vault import Vault


class UploadApiTests(unittest.TestCase):
    def test_upload_handler_preserves_binary_and_sanitizes_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(
                vault_path=Path(tmp) / "vault",
                runtime_path=Path(tmp) / "runtime",
                backup_path=Path(tmp) / "backups",
                evidence_path=Path(tmp) / "evidence",
                service_token="upload-token",
            )
            vault = Vault(settings.vault_path)
            vault.init()
            result = handle_upload(
                vault,
                Index(settings.runtime_path / "index.sqlite3"),
                settings,
                {"filename": "../receipt.pdf", "data_base64": base64.b64encode(b"%PDF-1.4\nBT (API Receipt) Tj ET\n%%EOF").decode("ascii")},
            )
            self.assertEqual(result["extraction"]["extracted_text"], "API Receipt")
            self.assertEqual(Path(result["attachment_path"]).name, result["source_id"] + ".pdf")


if __name__ == "__main__":
    unittest.main()
