"""Synthetic packaging boundary tests; native output is verified separately."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("stage_backend", Path(__file__).with_name("stage-backend.py"))
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)
bootstrap_spec = importlib.util.spec_from_file_location("packaged_backend", Path(__file__).with_name("packaged-backend.py"))
bootstrap = importlib.util.module_from_spec(bootstrap_spec)
bootstrap_spec.loader.exec_module(bootstrap)


class BundleBoundaries(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows atomic helper-copy path")
    def test_atomic_helper_copy_suffix_crosses_260_without_machine_changes(self):
        with tempfile.TemporaryDirectory(dir=stage.DESKTOP / "test-results") as temporary:
            root = Path(temporary)
            suffix = "/helper.safetensors"
            destination = root / ("x" * (254 - len(str(root)) - len(suffix) - 1)) / suffix[1:]
            self.assertEqual(len(str(destination)), 254)
            staging = destination.with_name(destination.name + ".copying")
            self.assertEqual(len(str(staging)), 262)
            extended = bootstrap.windows_io_path(staging)
            extended.parent.mkdir(parents=True)
            extended.write_bytes(b"synthetic-public-helper")
            extended.replace(bootstrap.windows_io_path(destination))
            self.assertEqual(destination.read_bytes(), b"synthetic-public-helper")

    @unittest.skipUnless(os.name == "nt", "Windows junction boundary")
    def test_inventory_rejects_a_junction_before_following_it(self):
        with tempfile.TemporaryDirectory(dir=stage.DESKTOP / "test-results") as temporary:
            root = Path(temporary)
            payload, outside = root / "payload", root / "outside-synthetic"
            payload.mkdir(); outside.mkdir()
            sentinel = outside / "fixture.txt"
            sentinel.write_text("synthetic-outside-payload")
            link = payload / "unexpected"
            quote = lambda value: "'" + str(value).replace("'", "''") + "'"
            shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
            subprocess.run([str(shell), "-NoProfile", "-Command",
                "New-Item -ItemType Junction -Path " + quote(link) + " -Target " + quote(outside) + " | Out-Null"],
                check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            with self.assertRaisesRegex(ValueError, "outside its root"):
                stage.inventory(payload)
            self.assertEqual(sentinel.read_text(), "synthetic-outside-payload")

    def test_source_refresh_preserves_selected_dependencies_and_refuses_lock_changes(self):
        with tempfile.TemporaryDirectory(dir=stage.DESKTOP / "test-results") as temporary:
            root = Path(temporary)
            repo, payload = root / "repo", root / "payload"
            repo.mkdir(); payload.mkdir()
            subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)
            def commit():
                subprocess.run(["git", "add", "."], cwd=repo, check=True)
                subprocess.run(["git", "-c", "user.name=Synthetic test", "-c",
                    "user.email=synthetic@example.invalid", "commit", "--quiet",
                    "-m", "Synthetic source refresh"], cwd=repo, check=True)
                return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            (repo / "runtime/renulus").mkdir(parents=True)
            (repo / "runtime/renulus/obsolete.py").write_text("synthetic-old-source")
            (repo / "uv.lock").write_text("synthetic-locked-wheels")
            before = commit()
            stage.snapshot(repo, before, payload)
            (payload / "dependencies").mkdir()
            (payload / "dependencies/fixture.bin").write_bytes(b"synthetic-selected-wheel")
            (repo / "runtime/renulus/obsolete.py").unlink()
            (repo / "runtime/renulus/new.py").write_text("synthetic-new-source")
            after = commit()
            stage.refresh_snapshot(repo, before, after, payload)
            self.assertFalse((payload / "runtime/renulus/obsolete.py").exists())
            self.assertEqual((payload / "runtime/renulus/new.py").read_text(), "synthetic-new-source")
            self.assertEqual((payload / "dependencies/fixture.bin").read_bytes(), b"synthetic-selected-wheel")
            (repo / "uv.lock").write_text("synthetic-different-wheels")
            changed = commit()
            with self.assertRaisesRegex(ValueError, "Dependency changes"):
                stage.refresh_snapshot(repo, after, changed, payload)
            self.assertEqual((payload / "uv.lock").read_text(), "synthetic-locked-wheels")

    def test_runtime_patch_preserves_other_changes_and_refuses_conflicting_source(self):
        with tempfile.TemporaryDirectory(dir=stage.DESKTOP / "test-results") as temporary:
            root = Path(temporary)
            repo, payload = root / "repo", root / "payload"
            relative = Path("runtime/renulus/runtime/api.py")
            original = "configured = False\n" + "# unchanged context\n" * 12
            for base in (repo, payload):
                (base / relative).parent.mkdir(parents=True)
                (base / relative).write_text(original, encoding="utf-8")
            subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)
            def commit():
                subprocess.run(["git", "add", "."], cwd=repo, check=True)
                subprocess.run(["git", "-c", "user.name=Synthetic test", "-c",
                                "user.email=synthetic@example.invalid", "commit", "--quiet",
                                "-m", "Synthetic runtime fixture"], cwd=repo, check=True)
            commit()
            (repo / relative).write_text(original.replace("False", "True"), encoding="utf-8")
            commit()
            (payload / relative).write_text(original + "# integrator addition\n", encoding="utf-8")
            proof = stage.apply_runtime_patch(repo, "HEAD", payload)
            self.assertEqual(proof["state"], "applied-to-generated-payload")
            self.assertIn("configured = True", (payload / relative).read_text())
            self.assertIn("# integrator addition", (payload / relative).read_text())
            self.assertEqual(stage.apply_runtime_patch(repo, "HEAD", payload)["state"], "already-included")
            conflicting = original.replace("False", "'custom'")
            (payload / relative).write_text(conflicting, encoding="utf-8")
            with self.assertRaises(subprocess.CalledProcessError):
                stage.apply_runtime_patch(repo, "HEAD", payload)
            self.assertEqual((payload / relative).read_text(), conflicting)
            self.assertEqual((repo / relative).read_text(), original.replace("False", "True"))

    def test_inventory_records_current_bytes_and_excludes_its_own_manifest(self):
        with tempfile.TemporaryDirectory(dir=stage.DESKTOP / "test-results") as temporary:
            root = Path(temporary)
            (root / "nested").mkdir()
            (root / "nested/binary").write_bytes(b"synthetic-new-bytes")
            (root / "inventory.json").write_text("stale inventory", encoding="utf-8")
            self.assertEqual(stage.inventory(root), [{
                "path": "nested/binary", "size": 19,
                "sha256": hashlib.sha256(b"synthetic-new-bytes").hexdigest(),
            }])

    def test_source_snapshot_includes_additive_migrations_and_excludes_private_state(self):
        with tempfile.TemporaryDirectory(dir=stage.DESKTOP / "test-results") as temporary:
            base = Path(temporary)
            repo, target = base / "source", base / "payload"
            repo.mkdir()
            target.mkdir()
            files = {
                "runtime/renulus/server.py": "# synthetic source\n",
                "runtime/renulus/cases/migrations/002_new.sql": "SELECT 1;",
                "upstream/hermes/agent/conversation_markers.py": "# preserved runtime",
                "upstream/hermes/hermes_cli/mem_trim.py": "# preserved runtime",
                "upstream/hermes/apps/desktop/private-fixture.json": "synthetic excluded",
                "upstream/hermes/tests/fixture.py": "synthetic excluded",
                "content/packs/original/manifest.json": "{}",
                "packaging/runtime/helper-assets.json": "{}",
                "uv.lock": "version = 1",
                "docs/SOURCES.md": "| K01 — Synthetic public source [Publisher](https://publisher.example) |",
                "docs/private-fixture.md": "synthetic excluded",
                ".local/credentials.json": "synthetic-secret-sentinel",
                ".venv/pyvenv.cfg": "synthetic-developer-wrapper",
                "apps/desktop/unrelated.txt": "synthetic excluded",
            }
            for name, value in files.items():
                file = repo / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(value, encoding="utf-8")
            subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "-c", "user.name=Synthetic test", "-c",
                            "user.email=synthetic@example.invalid", "commit", "--quiet",
                            "-m", "Synthetic packaging fixture"], cwd=repo, check=True)
            stage.snapshot(repo, "HEAD", target)
            admitted = {file.relative_to(target).as_posix() for file in target.rglob("*") if file.is_file()}
            self.assertEqual(admitted, {
                "runtime/renulus/server.py", "runtime/renulus/cases/migrations/002_new.sql",
                "upstream/hermes/agent/conversation_markers.py",
                "upstream/hermes/hermes_cli/mem_trim.py",
                "content/packs/original/manifest.json",
                "packaging/runtime/helper-assets.json", "uv.lock", "docs/SOURCES.md",
            })

    def contract_fixture(self, base):
        manifest = {"version": 1, "groups": {name: {"revision": "synthetic", "files": [
            {"path": name + "/fixture", "size": 4, "sha256": "0" * 64}]}
            for name in ("embedding", "docling", "ocr")}}
        contract = base / "reviewed.json"
        acquired = base / "helpers"
        acquired.mkdir()
        contract.write_text(json.dumps(manifest), encoding="utf-8")
        (acquired / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return contract, acquired, manifest

    def test_contract_accepts_identical_semantics_with_different_formatting(self):
        with tempfile.TemporaryDirectory(dir=stage.DESKTOP / "test-results") as temporary:
            contract, acquired, manifest = self.contract_fixture(Path(temporary))
            (acquired / "manifest.json").write_text(json.dumps(manifest, indent=4), encoding="utf-8-sig")
            self.assertEqual(stage.helper_contract(contract, acquired), manifest)

    def test_acquired_manifest_cannot_replace_reviewed_hash(self):
        with tempfile.TemporaryDirectory(dir=stage.DESKTOP / "test-results") as temporary:
            contract, acquired, manifest = self.contract_fixture(Path(temporary))
            modified = copy.deepcopy(manifest)
            modified["groups"]["embedding"]["files"][0]["sha256"] = "1" * 64
            (acquired / "manifest.json").write_text(json.dumps(modified), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "differs"):
                stage.helper_contract(contract, acquired)

    def test_extra_helper_group_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=stage.DESKTOP / "test-results") as temporary:
            contract, acquired, manifest = self.contract_fixture(Path(temporary))
            manifest["groups"]["unapproved"] = {}
            contract.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "selected groups"):
                stage.helper_contract(contract, acquired)


if __name__ == "__main__":
    unittest.main()
