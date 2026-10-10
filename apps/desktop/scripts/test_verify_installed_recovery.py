# SPDX-License-Identifier: MIT
"""Stdlib unit checks only; never load Renulus, engines or an installed app."""
import importlib.util
import copy
import hashlib
import shutil
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "installed_recovery", Path(__file__).with_name("verify-installed-recovery.py"))
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class AdmissionTests(unittest.TestCase):
    def test_user_cache_environment_and_network_cannot_escape(self):
        root = Path("C:/Renulus/scratch/design-c/delivery/r-0123abcd")
        supplied = {"SystemRoot": "C:/Windows", "USERPROFILE": "C:/Users/owner",
                    "APPDATA": "C:/Users/owner/AppData/Roaming", "OPENAI_API_KEY": "never-copy",
                    "PYTHONPATH": "C:/Renulus/dev/repo/runtime", "HTTP_PROXY": "https://external"}
        environment = driver.isolated_environment(root, supplied)
        for name in driver.ENV_PATHS:
            self.assertTrue(Path(environment[name]).is_relative_to(root), name)
        for name in ("OPENAI_API_KEY", "PYTHONPATH", "HTTP_PROXY"):
            self.assertNotIn(name, environment)
        boundary = driver.SafetyBoundary(root, root / "h", root / "b")
        boundary.check("socket.connect", (object(), ("127.0.0.1", 12345)))
        boundary.check("open", (str(root / "u/cache/a"), "w", 0))
        for event, args in (("socket.connect", (object(), ("203.0.113.1", 443))),
                            ("socket.getaddrinfo", ("provider.invalid", 443)),
                            ("open", ("C:/Renulus/data/learning/state/renulus.sqlite3", "r", 0)),
                            ("open", (str(root / "h/model.onnx"), "w", 0)),
                            ("open", (str(root / "b/state/renulus.sqlite3"), "w", 0)),
                            ("sqlite3.connect", ("file:C:/Renulus/data/learning/state/renulus.sqlite3?mode=ro",)),
                            ("subprocess.Popen", ("anything",))):
            with self.subTest(event=event, args=args), self.assertRaises(driver.ProofError):
                boundary.check(event, args)
        boundary.check("sqlite3.connect", ("file:" + str(root / "u/state/renulus.sqlite3") + "?mode=ro",))
        with self.assertRaises(PermissionError):
            boundary.check("os.symlink", ("synthetic-only", str(root / "e/probe")))
        self.assertEqual(boundary.reparse_refusals, 1)

    def test_installed_identity_refuses_source_interpreter_and_path_substitution(self):
        bundle = Path("C:/Renulus/scratch/design-c/delivery/installed-0123abcd/resources/backend")
        runtime = {"platform": "win32", "version": "3.14.4",
                   "executable": str(bundle / "python/python.exe"),
                   "prefix": str(bundle / "python"), "base_prefix": str(bundle / "python"),
                   "isolated": 1, "no_site": 1, "no_user_site": 1, "bytecode_disabled": True,
                   "sys_path": [str(bundle / path) for path in driver.PYTHON_PATHS]}
        metadata = {"format": "embedded-cpython-windows-v1", "source_revision": "a" * 40,
                    "python": {"version": "3.14.4", "executable": "python/python.exe"}}
        driver.validate_runtime(bundle, metadata, runtime, "a" * 40)
        for key, replacement in (("executable", "C:/Renulus/dev/python/Scripts/python.exe"),
                                 ("prefix", "C:/Renulus/data/learning"),
                                 ("isolated", 0), ("no_site", 0),
                                 ("bytecode_disabled", False), ("version", "3.14.3"),
                                 ("sys_path", runtime["sys_path"] + ["C:/Renulus/dev/repo/runtime"])):
            changed = {**runtime, key: replacement}
            with self.subTest(key=key), self.assertRaises(driver.ProofError):
                driver.validate_runtime(bundle, metadata, changed, "a" * 40)
        with self.assertRaises(driver.ProofError):
            driver.validate_runtime(bundle, metadata, runtime, "b" * 40)

    def test_exact_compact_run_and_profile_boundary(self):
        root = Path("C:/Renulus/scratch/design-c/delivery/r-0123abcd")
        self.assertEqual(driver.checked_run(root), root.resolve())
        self.assertEqual(driver.checked_profile(root, "z2"), (root / "z2").resolve())
        self.assertLessEqual(len(str(root / "z2")), 60)
        for value in ("C:/Renulus/data/learning",
                      "C:/Renulus/scratch/design-c/delivery/r-0123abcd/../r-9876abcd",
                      "C:/Renulus/scratch/design-c/delivery/r-0123abcd/u",
                      "C:/Renulus/scratch/design-c/delivery/r-ABCDEF12"):
            with self.subTest(value=value), self.assertRaises(driver.ProofError):
                driver.checked_run(Path(value))
        for name in ("../u", "learning", "u/../../owner", ""):
            with self.subTest(name=name), self.assertRaises(driver.ProofError):
                driver.checked_profile(root, name)


class FileGuardTests(unittest.TestCase):
    def setUp(self):
        lane = Path("C:/Renulus/scratch/design-c/dc-review-data/verifier-unit")
        lane.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="g-", dir=lane))

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_full_inventory_refuses_changed_extra_and_escaping_files(self):
        (self.root / "public.bin").write_bytes(b"original")
        records = [{"path": "public.bin", "size": 8,
                    "sha256": hashlib.sha256(b"original").hexdigest()}]
        driver.validate_inventory(self.root, records)
        (self.root / "public.bin").write_bytes(b"modified")
        with self.assertRaises(driver.ProofError):
            driver.validate_inventory(self.root, records)
        (self.root / "public.bin").write_bytes(b"original")
        (self.root / "extra.bin").write_bytes(b"extra")
        with self.assertRaises(driver.ProofError):
            driver.validate_inventory(self.root, records)
        for path in ("../private", "/absolute", "a\\b", "C:/private", "a/../public.bin"):
            with self.subTest(path=path), self.assertRaises(driver.ProofError):
                driver.relative_file(self.root, path)
        with self.assertRaises(driver.ProofError):
            driver.relative_file(self.root, "a" + chr(92) + "b")

    def test_phase_receipt_is_parseable_and_never_overwrites_old_evidence(self):
        path = self.root / "prepared.json"
        driver.write_json(path, {"phase": "prepared", "identity": "exact"})
        self.assertEqual(driver.read_json(path), {"phase": "prepared", "identity": "exact"})
        with self.assertRaises(FileExistsError):
            driver.write_json(path, {"phase": "replacement"})

    def seed(self):
        (self.root / "u/state").mkdir(parents=True)
        # These are guard bytes, not an invented database or migration fixture.
        (self.root / "u/state/renulus.sqlite3").write_bytes(b"guard-only")
        for name in ("old.json", "old1.zip", "old2.zip"):
            (self.root / name).write_bytes(b"guard-only")
        files = [{"path": name, "size": path.stat().st_size, "sha256": driver.sha256(path)}
                 for name, path in driver.files_in(self.root).items()]
        return {"format": driver.SEED_FORMAT, "old_commit": driver.OLD_COMMIT,
                "run_root": str(self.root), "profile": str(self.root / "u"),
                "synthetic": True, "closed": True, "schema_version": 1,
                "old_source_archive_sha256": "a" * 64, "seed_driver_sha256": "b" * 64,
                "fixture_sha256": "c" * 64, "files": files,
                "exports": {"json": "old.json", "zip1": "old1.zip", "zip2": "old2.zip"}}

    def test_seed_manifest_is_complete_and_cannot_redirect_to_owner(self):
        seed = self.seed()
        driver.validate_seed_files(self.root, seed)
        for field, value in (("old_commit", "0" * 40), ("profile", "C:/Renulus/data/learning"),
                             ("closed", False), ("synthetic", False), ("schema_version", 2),
                             ("exports", {"json": "../outside.json", "zip1": "old1.zip", "zip2": "old2.zip"})):
            with self.subTest(field=field), self.assertRaises(driver.ProofError):
                driver.validate_seed_files(self.root, {**seed, field: value})
        (self.root / "u/state/connections.dpapi").write_bytes(b"refused")
        with self.assertRaises(driver.ProofError):
            driver.validate_seed_files(self.root, seed)

    def test_seed_rejects_even_manifested_credentials_open_wal_and_file_mutation(self):
        seed = self.seed()
        for name in ("u/state/runtime/connections.dpapi", "u/state/renulus.sqlite3-wal"):
            altered = copy.deepcopy(seed)
            altered["files"].append({"path": name, "size": 0, "sha256": "d" * 64})
            with self.subTest(name=name), self.assertRaises(driver.ProofError):
                driver.validate_seed_files(self.root, altered)
        (self.root / "old.json").write_bytes(b"guard-changed")
        with self.assertRaises(driver.ProofError):
            driver.validate_seed_files(self.root, seed)


class EvidenceAssertions(unittest.TestCase):
    def original_fixture(self):
        # Descriptors exercise driver guards only, never an invented database.
        digest = hashlib.sha256(b"synthetic original").hexdigest()
        stored = [{"id": "present", "document_id": "doc-present", "bytes": 18,
                   "sha256": digest, "original_path": "library/knowledge/doc-present/present/original.txt"},
                  {"id": "absent", "document_id": "doc-absent", "bytes": 37,
                   "sha256": "a" * 64, "original_path": None}]
        originals = [{"revision_id": "present", "document_id": "doc-present", "bytes": 18,
                      "sha256": digest, "path": stored[0]["original_path"]}]
        inventory = {originals[0]["path"]: {"size": 18, "sha256": digest}}
        return stored, originals, inventory

    def test_seed_original_expectations_are_explicit_and_immutable(self):
        stored, originals, inventory = self.original_fixture()
        present, absent = driver.library_original_expectations(stored, originals, inventory)
        self.assertEqual(set(present), {"present"})
        self.assertEqual(absent, frozenset({"absent"}))
        with self.assertRaises(TypeError):
            present["present"] = ("changed", 0, "b" * 64)
        with self.assertRaises(AttributeError):
            absent.add("present")

    def test_lost_seed_original_cannot_be_reclassified_as_expected_absence(self):
        stored, originals, inventory = self.original_fixture()
        stored[0]["original_path"] = None
        with self.assertRaisesRegex(driver.ProofError, "Archived original missing"):
            driver.library_original_expectations(stored, originals, inventory)
        stored, originals, inventory = self.original_fixture()
        for altered in ({}, {originals[0]["path"]: {"size": 18, "sha256": "b" * 64}}):
            with self.subTest(inventory=altered), self.assertRaises(driver.ProofError):
                driver.library_original_expectations(stored, originals, altered)
        # Even if an archive entry were omitted too, another valid original
        # cannot make the inventoried lost revision eligible for the absent set.
        other = {**stored[0], "id": "other", "document_id": "doc-other",
                 "original_path": "library/knowledge/doc-other/other/original.txt"}
        archive_other = {**originals[0], "revision_id": "other", "document_id": "doc-other", "path": other["original_path"]}
        stored[0]["original_path"] = None
        with self.assertRaisesRegex(driver.ProofError, "Inventoried original missing"):
            driver.library_original_expectations([*stored, other], [archive_other],
                {**inventory, other["original_path"]: {"size": 18, "sha256": other["sha256"]}})

    def test_seed_and_both_archive_identities_must_agree_and_include_real_bytes(self):
        stored, originals, inventory = self.original_fixture()
        for field, value in (("revision_id", "absent"), ("document_id", "wrong-document"),
                             ("bytes", 0), ("sha256", "b" * 64), ("path", "another-original.txt")):
            changed = [{**originals[0], field: value}]
            with self.subTest(field=field), self.assertRaises(driver.ProofError):
                driver.library_original_expectations(stored, changed, inventory)
        with self.assertRaises(driver.ProofError):
            driver.library_original_expectations(stored, originals * 2, inventory)
        with self.assertRaises(driver.ProofError):
            driver.library_original_expectations([stored[1]], [], {})

    def test_target_missing_paths_never_override_frozen_or_new_presence(self):
        stored, originals, inventory = self.original_fixture()
        expectations = driver.library_original_expectations(stored, originals, inventory)
        # JSON correctly clears all paths. Even after that clearing, previously
        # present and unknown/current identities must demand an actual original
        # when the full-ZIP original assertion runs.
        target = [{**row, "original_path": None} for row in stored]
        target.append({**target[0], "id": "new-current", "document_id": "new-document"})
        expected, unavailable = driver.partition_library_originals(target, expectations)
        self.assertEqual([row["id"] for row in expected], ["present", "new-current"])
        self.assertEqual([row["id"] for row in unavailable], ["absent"])
        for changed in (target[1:], [{**target[0], "sha256": "b" * 64}, *target[1:]]):
            with self.subTest(changed=changed), self.assertRaises(driver.ProofError):
                driver.partition_library_originals(changed, expectations)

    def test_actual_original_assertion_propagates_missing_present_and_new_errors(self):
        stored, originals, inventory = self.original_fixture()
        expectations = driver.library_original_expectations(stored, originals, inventory)
        calls = []
        class MissingOriginal:
            def original(self, identifier):
                calls.append(identifier)
                raise FileNotFoundError(identifier)
        class GuardServices:
            def get(self, name):
                assert name == "knowledge"
                return MissingOriginal()
        new = {**stored[0], "id": "new-current", "original_path": None}
        for library, identifier in ((stored, "present"), ([new, *stored], "new-current")):
            with self.subTest(identifier=identifier), self.assertRaisesRegex(FileNotFoundError, identifier):
                driver.assert_originals(GuardServices(), library, [], expectations=expectations)
            self.assertEqual(calls[-1], identifier)

    def test_rebuild_requires_changed_generations_count_and_actual_hit(self):
        before = {"knowledge": "old-library", "memory": "old-memory"}
        after = {"knowledge": "new-library", "memory": "new-memory"}
        report = {"status": "complete", "modules": {
            "knowledge": {"status": "complete", "rebuilt_unit": "passages", "rebuilt_records": 1},
            "memory": {"status": "complete", "rebuilt_unit": "records", "rebuilt_records": 2}}}
        driver.assert_effective_rebuild(before, after, report, ["known-revision"], ["known-fact"],
                                        revision="known-revision", fact="known-fact")
        for changed in (before, {**after, "knowledge": None}):
            with self.subTest(changed=changed), self.assertRaises(driver.ProofError):
                driver.assert_effective_rebuild(before, changed, report, ["known-revision"], ["known-fact"],
                                                revision="known-revision", fact="known-fact")
        for passages, facts in (([], ["known-fact"]), (["other"], ["known-fact"]), (["known-revision"], [])):
            with self.subTest(passages=passages, facts=facts), self.assertRaises(driver.ProofError):
                driver.assert_effective_rebuild(before, after, report, passages, facts,
                                                revision="known-revision", fact="known-fact")
        altered = copy.deepcopy(report)
        altered["modules"]["memory"]["rebuilt_records"] = 0
        with self.assertRaises(driver.ProofError):
            driver.assert_effective_rebuild(before, after, altered, ["known-revision"], ["known-fact"],
                                            revision="known-revision", fact="known-fact")

    def test_preserved_partial_score_and_pin_assertions_detect_data_loss(self):
        expected = [{"id": "old-answer", "correct": 1, "assisted": 1, "score_bucket": "assisted",
                     "snapshot_json": "original immutable pin", "item_count": 3}]
        driver.assert_preserved_rows(expected, [{**expected[0], "new_column": None}], "legacy")
        for key, value in (("correct", 0), ("assisted", 0), ("item_count", 1),
                           ("snapshot_json", "reselected current pin")):
            with self.subTest(key=key), self.assertRaises(driver.ProofError):
                driver.assert_preserved_rows(expected, [{**expected[0], key: value}], "legacy")
        with self.assertRaises(driver.ProofError):
            driver.assert_preserved_rows(expected, [], "legacy")


if __name__ == "__main__":
    unittest.main()
