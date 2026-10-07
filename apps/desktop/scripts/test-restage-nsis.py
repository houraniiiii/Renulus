"""Packaging-only regression checks with public templates and synthetic archives."""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("restage_nsis", Path(__file__).with_name("restage-nsis.py"))
nsis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nsis)
delivery_spec = importlib.util.spec_from_file_location("stage_delivery", Path(__file__).with_name("stage-delivery.py"))
delivery = importlib.util.module_from_spec(delivery_spec)
delivery_spec.loader.exec_module(delivery)
PUBLIC_MODULES = Path("E:/Renulus-native-delivery/desktop-20261005/environment/node-3ff9b0d6/node_modules")


class NsisPackagingTests(unittest.TestCase):
    def setUp(self):
        scratch = nsis.generated_path(Path(__file__).resolve().parents[1] / "test-results/nsis-regression")
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def factory_fixture(self):
        modules = self.root / "node_modules"
        for name in ("app-builder-lib", "electron-builder"):
            (modules / name).mkdir(parents=True)
            shutil.copyfile(PUBLIC_MODULES / name / "package.json", modules / name / "package.json")
        for name in nsis.FACTORY_SHA256:
            destination = modules / "app-builder-lib" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PUBLIC_MODULES / "app-builder-lib" / name, destination)
        return modules

    def test_original_public_factory_satisfies_pins(self):
        self.assertEqual(nsis.verify_factory(PUBLIC_MODULES)["version"], nsis.BUILDER_VERSION)

    def test_factory_mutation_is_refused_without_writes(self):
        modules = self.factory_fixture()
        file = modules / "app-builder-lib/templates/nsis/multiUser.nsh"
        file.write_bytes(file.read_bytes() + b"\n; synthetic unreviewed change\n")
        with self.assertRaisesRegex(ValueError, "Pinned factory bytes changed"):
            nsis.verify_factory(modules)
        self.assertIn(b"synthetic unreviewed change", file.read_bytes())

    def test_new_factory_root_is_not_silently_admitted(self):
        modules = self.factory_fixture()
        (modules / "app-builder-lib/templates/nsis/synthetic-extra.nsh").write_text("; synthetic")
        with self.assertRaisesRegex(ValueError, "root include set changed"):
            nsis.verify_factory(modules)

    def test_builder_version_and_licence_must_match(self):
        modules = self.factory_fixture()
        file = modules / "app-builder-lib/package.json"
        metadata = json.loads(file.read_text(encoding="utf-8"))
        metadata["version"] = "synthetic-other-version"
        file.write_text(json.dumps(metadata), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "pinned public MIT builder"):
            nsis.verify_factory(modules)

    def test_existing_policy_checkpoint_is_preserved(self):
        target = self.root / "policy"
        target.mkdir()
        sentinel = target / "preserved.txt"
        sentinel.write_text("synthetic checkpoint")
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            nsis.prepare(PUBLIC_MODULES, self.root / "absent-cache", target, "a" * 40, self.root / "install")
        self.assertEqual(sentinel.read_text(), "synthetic checkpoint")

    def test_archive_pin_refusal_precedes_policy_creation(self):
        cache = self.root / "cache"
        archive = cache / nsis.ARCHIVES["nsis"][0]
        archive.parent.mkdir(parents=True)
        archive.write_bytes(b"synthetic wrong archive")
        target = self.root / "policy"
        with self.assertRaisesRegex(ValueError, "differs from its pin"):
            nsis.prepare(PUBLIC_MODULES, cache, target, "a" * 40, self.root / "install")
        self.assertFalse(target.exists())

    def write_tar(self, names, link=False):
        archive = self.root / "synthetic.tar.gz"
        with tarfile.open(archive, "w:gz") as contents:
            for name in names:
                member = tarfile.TarInfo(name)
                if link:
                    member.type = tarfile.SYMTYPE
                    member.linkname = "../../outside"
                    contents.addfile(member)
                else:
                    data = b"synthetic public tool fixture"
                    member.size = len(data)
                    contents.addfile(member, io.BytesIO(data))
        return archive

    def test_synthetic_archive_is_copied_and_byte_verified(self):
        archive = self.write_tar(["bundle/LICENSE", "bundle/bin/tool.txt"])
        result = nsis.extract_toolset(archive, self.root / "toolset")
        self.assertEqual(len(result["files"]), 2)
        self.assertEqual((self.root / "toolset/bin/tool.txt").read_bytes(), b"synthetic public tool fixture")

    def test_archive_traversal_case_collision_and_links_fail_before_output(self):
        for names, link in ((["bundle/../../escape"], False), (["bundle/File", "bundle/file"], False), (["bundle/link"], True)):
            with self.subTest(names=names):
                archive = self.write_tar(names, link=link)
                target = self.root / "uncreated-toolset"
                with self.assertRaises(ValueError):
                    nsis.extract_toolset(archive, target)
                self.assertFalse(target.exists())

    def test_cache_patch_keeps_other_factory_operations_and_has_exact_copy_guard(self):
        original = (PUBLIC_MODULES / "app-builder-lib/templates/nsis/include/installUtil.nsh").read_text(encoding="utf-8")
        result = nsis.cache_macro(original, self.root / "policy", "a" * 40)
        self.assertIn("APP_INSTALLER_STORE_FILE", result)
        self.assertIn("$EXEPATH", result)
        self.assertIn("Renulus cache copy requires the current public installer", result)
        self.assertEqual(original.split("Function GetInQuotes", 1)[1], result.split("Function GetInQuotes", 1)[1])
        with self.assertRaisesRegex(ValueError, "copyFile macro"):
            nsis.cache_macro(original.replace("CopyFiles /SILENT", "CopyFiles"), self.root, "a" * 40)

    def test_nsis_path_cannot_inject_source(self):
        for name in ('bad"path', "bad$path", "bad" + chr(96) + "path", "bad\npath"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                nsis.nsis_path(self.root / name)

    def test_fixture_markers_cannot_satisfy_manufacture_gate(self):
        root = self.root / "policy"
        (root / "preflight").mkdir(parents=True)
        policy = {"root": str(root), "source_revision": "a" * 40}
        for name in ("compiled-factory.log", "compiled-guard.log", "compiled-cache.log"):
            (root / "preflight" / name).write_text(policy["source_revision"])
        with self.assertRaisesRegex(ValueError, "Actual manufacture compiler receipt"):
            nsis.verify_compiler_markers(policy)

    def test_preflight_failure_blocks_payload_inventory_copy_and_build(self):
        temporary = self.root / "temporary/build"
        payload = self.root / "payload-new"
        plan = {"base_payload": str(self.root / "payload-original"), "payload": str(payload),
                "temporary_directory": str(temporary), "package": "installer", "public_node_modules": str(PUBLIC_MODULES),
                "public_build_cache": str(self.root / "cache"), "source_revision": "a" * 40}
        with patch.object(delivery, "EXTERNAL_DELIVERY_ROOT", self.root), \
             patch.object(delivery, "checked_delivery_root", return_value=self.root), \
             patch.object(delivery.nsis, "prepare", return_value={}), \
             patch.object(delivery.nsis, "preflight", side_effect=ValueError("synthetic compiler refusal")), \
             patch.object(delivery.backend, "inventory") as inventory, \
             patch.object(delivery.shutil, "copytree") as copy, \
             patch.object(delivery.subprocess, "run") as build:
            with self.assertRaisesRegex(ValueError, "synthetic compiler refusal"):
                delivery.execute(plan)
            inventory.assert_not_called()
            copy.assert_not_called()
            build.assert_not_called()
        self.assertFalse(payload.exists())

    def test_public_dependency_copy_verifies_bytes_and_excludes_caches(self):
        source, target = self.root / "modules-original", self.root / "modules-copy"
        (source / ".cache").mkdir(parents=True)
        (source / "public-tool.dll").write_bytes(b"synthetic public tool")
        (source / ".cache/ignored.txt").write_text("synthetic ignored cache")
        result = delivery.copy_public_modules(source, target, self.root / "node-receipt.json")
        self.assertEqual(result["files"], 1)
        self.assertFalse((target / ".cache").exists())
        self.assertEqual((target / "public-tool.dll").read_bytes(), b"synthetic public tool")

    def test_dependency_copy_corruption_blocks_manufacture(self):
        source, target = self.root / "modules-original", self.root / "modules-copy"
        source.mkdir()
        (source / "public-tool.dll").write_bytes(b"synthetic public tool")
        copy = shutil.copytree
        def corrupt(*args, **kwargs):
            copy(*args, **kwargs)
            (target / "public-tool.dll").write_bytes(b"synthetic altered copy")
        with patch.object(delivery.shutil, "copytree", side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, "full byte inventory"):
                delivery.copy_public_modules(source, target, self.root / "node-receipt.json")
        self.assertFalse((self.root / "node-receipt.json").exists())


if __name__ == "__main__":
    unittest.main()
