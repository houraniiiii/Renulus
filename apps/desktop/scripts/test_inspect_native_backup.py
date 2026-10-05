"""Synthetic archive integrity checks; no native or real-producer claim."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile

spec = importlib.util.spec_from_file_location("native_backup_inspector", Path(__file__).with_name("inspect-native-backup.py"))
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


class NativeArchiveIntegrity(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / "test-results"
        root.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="inspect-", dir=root)
        self.addCleanup(self.temporary.cleanup)
        self.archive = Path(self.temporary.name) / "synthetic.zip"
        self.identifier, self.text = "mem_synthetic_native", "Synthetic study goal"
        self.segment = json.dumps({"id": self.identifier, "text": self.text}).encode() + b"\n"
        self.original = b"Synthetic retained text original"
        self.segment_path = "canonical/memory_facts/000000.jsonl"
        self.original_path = "library/knowledge/doc_synthetic/rev_synthetic/original.txt"
        self.manifest = {
            "format": "renulus-full-backup", "format_version": 2, "schema_version": 1,
            "exported_at": "2026-10-05T00:00:00Z", "omissions": {},
            "canonical": {"records": 1, "bytes": len(self.segment), "tables": {"memory_facts": 1},
                          "segments": [{"path": self.segment_path, "table": "memory_facts", "records": 1,
                                        "bytes": len(self.segment), "sha256": hashlib.sha256(self.segment).hexdigest()}]},
            "originals": [{"path": self.original_path, "bytes": len(self.original),
                           "sha256": hashlib.sha256(self.original).hexdigest()}],
        }

    def write(self, *, extra=None, duplicate=False):
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr(self.segment_path, self.segment)
            archive.writestr(self.original_path, self.original)
            archive.writestr("manifest.json", json.dumps(self.manifest))
            if extra:
                archive.writestr(extra, b"Synthetic undeclared bytes")
            if duplicate:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    archive.writestr(self.segment_path, self.segment)

    def inspect(self):
        return inspector.inspect(self.archive, expected_id=self.identifier, expected_text=self.text)

    def test_complete_synthetic_inventory_and_expected_row(self):
        self.write()
        result = self.inspect()
        self.assertTrue(result["synthetic_memory_present"])
        self.assertEqual((result["canonical_records"], result["originals"]), (1, 1))

    def test_changed_segment_hash_is_rejected(self):
        self.manifest["canonical"]["segments"][0]["sha256"] = "0" * 64
        self.write()
        with self.assertRaisesRegex(ValueError, "segment differs"):
            self.inspect()

    def test_changed_original_hash_is_rejected(self):
        self.manifest["originals"][0]["sha256"] = "0" * 64
        self.write()
        with self.assertRaisesRegex(ValueError, "original differs"):
            self.inspect()

    def test_missing_expected_manual_row_is_rejected(self):
        self.write()
        with self.assertRaisesRegex(ValueError, "omitted"):
            inspector.inspect(self.archive, expected_id="mem_absent", expected_text=self.text)

    def test_undeclared_member_is_rejected(self):
        self.write(extra="synthetic-undeclared.json")
        with self.assertRaisesRegex(ValueError, "inventory disagrees"):
            self.inspect()

    def test_duplicate_segment_is_rejected(self):
        self.write(duplicate=True)
        with self.assertRaisesRegex(ValueError, "duplicate members"):
            self.inspect()


if __name__ == "__main__":
    unittest.main()
