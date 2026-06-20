import tempfile
import unittest
from pathlib import Path

from cogni_life_os.integrity import scan
from cogni_life_os.vault import Vault


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Vault(Path(self.tmp.name) / "vault")
        self.vault.init()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, frontmatter, body):
        return self.vault.write_note(rel, frontmatter, body, expected_hash=None)

    def test_forward_reference_by_id_is_valid(self):
        self.write("30-concepts/a.md", {"id": "concept-a", "type": "concept"}, "links [[concept-b]]")
        self.write("30-concepts/b.md", {"id": "concept-b", "type": "concept"}, "target")
        self.assertEqual(scan(self.vault)["broken_links"], [])

    def test_backward_reference_by_id_is_valid(self):
        self.write("30-concepts/b.md", {"id": "concept-b", "type": "concept"}, "target")
        self.write("30-concepts/a.md", {"id": "concept-a", "type": "concept"}, "links [[concept-b]]")
        self.assertEqual(scan(self.vault)["broken_links"], [])

    def test_alias_reference_is_valid(self):
        self.write(
            "20-entities/people/raj.md",
            {"id": "person-raj", "type": "entity", "aliases": ["Raj Rawat", "Raj"]},
            "target",
        )
        self.write("30-concepts/a.md", {"id": "concept-a", "type": "concept"}, "links [[Raj Rawat]]")
        self.assertEqual(scan(self.vault)["broken_links"], [])

    def test_missing_target_is_reported(self):
        self.write("30-concepts/a.md", {"id": "concept-a", "type": "concept"}, "links [[missing-target]]")
        broken = scan(self.vault)["broken_links"]
        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0]["to"], "missing-target")

    def test_duplicate_ids_are_reported(self):
        self.write("30-concepts/a.md", {"id": "dup", "type": "concept"}, "a")
        self.write("30-concepts/b.md", {"id": "dup", "type": "concept"}, "b")
        self.assertEqual(scan(self.vault)["duplicate_ids"][0]["id"], "dup")

    def test_malformed_frontmatter_is_reported(self):
        path = self.vault.root / "30-concepts/bad.md"
        path.write_text("---\nid: bad\n# no close\n", encoding="utf-8")
        self.assertIn("30-concepts/bad.md", scan(self.vault)["malformed_frontmatter"])

    def test_renamed_target_still_valid_by_id(self):
        self.write("30-concepts/renamed-file.md", {"id": "stable-id", "type": "concept"}, "target")
        self.write("30-concepts/a.md", {"id": "concept-a", "type": "concept"}, "links [[stable-id]]")
        self.assertEqual(scan(self.vault)["broken_links"], [])

    def test_circular_links_are_valid(self):
        self.write("30-concepts/a.md", {"id": "a", "type": "concept"}, "[[b]]")
        self.write("30-concepts/b.md", {"id": "b", "type": "concept"}, "[[a]]")
        self.assertEqual(scan(self.vault)["broken_links"], [])

    def test_attachment_links_are_validated(self):
        attachment = self.vault.root / "10-sources/attachments/file.txt"
        attachment.parent.mkdir(parents=True, exist_ok=True)
        attachment.write_text("hello", encoding="utf-8")
        self.write("30-concepts/a.md", {"id": "a", "type": "concept"}, "[[10-sources/attachments/file.txt]]")
        self.write("30-concepts/b.md", {"id": "b", "type": "concept"}, "[[10-sources/attachments/missing.txt]]")
        result = scan(self.vault)
        self.assertEqual(len(result["missing_attachments"]), 1)
        self.assertEqual(result["missing_attachments"][0]["to"], "10-sources/attachments/missing.txt")


if __name__ == "__main__":
    unittest.main()
