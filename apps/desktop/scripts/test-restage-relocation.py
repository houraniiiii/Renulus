"""New relocation checks only; the completed factory/regression batch is retained."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from delivery_paths import DESKTOP, EXTERNAL_DELIVERY_ROOT, PUBLIC_INPUT_ROOT, checked_delivery_root, generated_path, public_input_path

spec = importlib.util.spec_from_file_location("stage_delivery", Path(__file__).with_name("stage-delivery.py"))
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class RelocatedPaths(unittest.TestCase):
    def test_root_configuration_admits_only_canonical_or_one_named_c_child(self):
        named = EXTERNAL_DELIVERY_ROOT / "deliveries/relocation-check-never-created"
        for root in (EXTERNAL_DELIVERY_ROOT, named):
            self.assertEqual(checked_delivery_root(root), root.resolve())
        self.assertEqual(generated_path(named / "matching-cafe1234/never-created", fresh=True),
                         (named / "matching-cafe1234/never-created").resolve())
        self.assertFalse(named.exists())
        for root in (PUBLIC_INPUT_ROOT, Path("C:relative"),
                     EXTERNAL_DELIVERY_ROOT / "repo", EXTERNAL_DELIVERY_ROOT / "data",
                     EXTERNAL_DELIVERY_ROOT / "profiles", EXTERNAL_DELIVERY_ROOT / "credentials",
                     EXTERNAL_DELIVERY_ROOT / "deliveries", named / "extra",
                     EXTERNAL_DELIVERY_ROOT / "deliveries/Uppercase",
                     EXTERNAL_DELIVERY_ROOT / "deliveries/nul",
                     EXTERNAL_DELIVERY_ROOT / "deliveries/nul.txt",
                     EXTERNAL_DELIVERY_ROOT / "deliveries/alias."):
            with self.subTest(root=root), self.assertRaises(ValueError):
                checked_delivery_root(root)

    def test_root_guard_rejects_a_reparse_ancestor_before_any_write(self):
        named = EXTERNAL_DELIVERY_ROOT / "deliveries/relocation-check-never-created"
        with patch.object(Path, "is_junction", lambda path: path == named):
            with self.assertRaisesRegex(ValueError, "reparse"):
                checked_delivery_root(named)
        self.assertFalse(named.exists())

    def test_public_inputs_remain_on_e_and_new_generated_paths_are_on_c(self):
        self.assertEqual(EXTERNAL_DELIVERY_ROOT, Path("C:/Renulus-native-delivery/desktop-20261005"))
        self.assertEqual(PUBLIC_INPUT_ROOT, Path("E:/Renulus-native-delivery/desktop-20261005"))
        public = PUBLIC_INPUT_ROOT / "payloads/backend-55d553d1"
        self.assertEqual(public_input_path(public), public.resolve())
        for root in (EXTERNAL_DELIVERY_ROOT, PUBLIC_INPUT_ROOT):
            for family in ("environment/node-3ff9b0d6/node_modules",
                           "preparation/restage-office-image-20261005/public-build-cache/electron-builder"):
                self.assertEqual(public_input_path(root / family), (root / family).resolve())
        with self.assertRaisesRegex(ValueError, "read-only"):
            generated_path(public)
        target = EXTERNAL_DELIVERY_ROOT / "matching-cafe1234/relocation-check-never-created"
        self.assertEqual(generated_path(target, fresh=True), target.resolve())
        self.assertFalse(target.exists())

    def test_read_and_write_resolvers_refuse_repository_data_siblings_and_traversal(self):
        for root in (EXTERNAL_DELIVERY_ROOT, PUBLIC_INPUT_ROOT):
            for target in (root, root / "repo/private", root / "data/learning", root / "profiles/native",
                           root / "credentials/auth.json", root / ".codex/auth.json", root / "temporary/../../outside"):
                with self.subTest(target=target), self.assertRaises(ValueError):
                    public_input_path(target)
                with self.subTest(output=target), self.assertRaises(ValueError):
                    generated_path(target)
            with self.assertRaises(ValueError):
                public_input_path(root.parent / "desktop-20261005-other/payloads/public")
        # These are refused lexically, without opening any credential or data file.
        for target in (Path("C:/Users/karol/.codex/auth.json"),
                       Path("E:/Renulus-data/collection/private.pdf"), Path("C:relative")):
            for resolver in (public_input_path, generated_path):
                with self.subTest(target=target, resolver=resolver.__name__), self.assertRaises(ValueError):
                    resolver(target)

    def test_selected_root_cannot_output_into_another_delivery_or_repository(self):
        root = EXTERNAL_DELIVERY_ROOT / "deliveries/relocation-check-never-created"
        output = root / "matching-cafe1234"
        self.assertEqual(delivery.delivery_output(output, root=root), output.resolve())
        for target in (EXTERNAL_DELIVERY_ROOT / "matching-cafe1234", root / "repo",
                       PUBLIC_INPUT_ROOT / "matching-cafe1234"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                delivery.delivery_output(target, root=root)
        self.assertFalse(root.exists())

    def test_recovered_factory_receipt_proves_no_installer_execution(self):
        root = DESKTOP / "test-results/nsis-full-factory-03"
        if not (root / "preflight-evidence.json").is_file():
            self.skipTest("Recovery receipts stay in the packaging worktree; no new compiler run")
        evidence = json.loads((root / "preflight-evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["status"], "passed")
        self.assertFalse(evidence["installer_execution"])
        self.assertEqual(len(evidence["factory_root_includes"]), 7)
        self.assertIn("schema passed", evidence["supported_local_toolsets"])
        self.assertEqual([r["exit"] for r in evidence["receipts"]], [0, 0, 1, 0, 0, 0, 0])
        for output in evidence["outputs"]:
            file = Path(output["path"])
            self.assertEqual(file.stat().st_size, output["bytes"])
            with file.open("rb") as stream:
                self.assertEqual(hashlib.file_digest(stream, "sha256").hexdigest(), output["sha256"])
        for name in ("compiled-factory.log", "compiled-guard.log", "compiled-cache.log"):
            self.assertFalse((root / name).exists())
            self.assertTrue((root / "preflight" / name).is_file())

    def test_relocated_plan_is_read_only_and_separates_public_reuse_from_new_source(self):
        revision = "9d26f1eedf31cd488b9aab5837a105ee152d9efa"
        args = argparse.Namespace(
            source=DESKTOP.parents[1], revision=revision,
            delivery_root=EXTERNAL_DELIVERY_ROOT,
            payload=PUBLIC_INPUT_ROOT / "payloads/backend-55d553d1",
            snapshot=EXTERNAL_DELIVERY_ROOT / "source-9d26f1ee",
            output=EXTERNAL_DELIVERY_ROOT / "matching-9d26f1ee",
            environment=Path("C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv"),
            helpers=PUBLIC_INPUT_ROOT / "payloads/backend-55d553d1/helper-assets",
            python_archive=PUBLIC_INPUT_ROOT / "preparation/restage-office-image-20261005/inputs/python-3.14.4-embed-amd64.zip",
            node_modules=EXTERNAL_DELIVERY_ROOT / "environment/node-3ff9b0d6/node_modules",
            build_cache=PUBLIC_INPUT_ROOT / "preparation/restage-office-image-20261005/public-build-cache/electron-builder",
            package="installer", resume_staged=False)
        result = delivery.plan(args)
        for name in ("snapshot", "output", "payload", "build_node_modules", "temporary_directory"):
            value = Path(result[name])
            self.assertTrue(value.is_relative_to(EXTERNAL_DELIVERY_ROOT))
            self.assertFalse(value.exists(), name)
        for name in ("base_payload", "public_build_cache"):
            self.assertTrue(Path(result[name]).is_relative_to(PUBLIC_INPUT_ROOT), name)
        self.assertEqual(Path(result["public_node_modules"]), args.node_modules.resolve())
        self.assertEqual(Path(result["environment"]["RENULUS_DELIVERY_ROOT"]), EXTERNAL_DELIVERY_ROOT)
        self.assertEqual(result["environment"]["ELECTRON_BUILDER_COMPRESSION_LEVEL"], "1")
        self.assertIn("--refresh-source-only", result["commands"][0])
        self.assertIn("--include-native", result["commands"][1])
        self.assertEqual(result["helper_files"], 19)
        receipt = DESKTOP / "test-results/relocated-plan.json"
        receipt.write_text(json.dumps({"plan_only": True, **result}, indent=2), encoding="utf-8")


class RelocatedBuilderConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scratch = DESKTOP / "test-results/relocation-config"
        scratch.mkdir(parents=True, exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=scratch)
        cls.addClassCleanup(cls.temp.cleanup)
        cls.bundle = Path(cls.temp.name) / "synthetic-backend"
        (cls.bundle / "python").mkdir(parents=True)
        (cls.bundle / "python/python.exe").write_bytes(b"synthetic placeholder, never executed")
        (cls.bundle / "inventory.json").write_text("[]")
        (cls.bundle / "bundle.json").write_text(json.dumps({
            "version": 1, "format": "embedded-cpython-windows-v1",
            "python": {"executable": "python/python.exe"}}))

    def config(self, output, root=None, junction=False):
        environment = dict(os.environ)
        for name in ("RENULUS_RENDERER_BUNDLE", "RENULUS_NATIVE_BUNDLE", "RENULUS_DELIVERY_ROOT"):
            environment.pop(name, None)
        environment.update(RENULUS_DELIVERY_OUTPUT=str(output), RENULUS_DELIVERY_REVISION="a" * 40,
                           RENULUS_BACKEND_BUNDLE=str(self.bundle))
        if root is not None:
            environment["RENULUS_DELIVERY_ROOT"] = str(root)
        # Simulate one junction at the guarded output without touching C staging.
        code = """
const fs = require('node:fs');
if (process.argv[2] === 'junction') {
  const original = fs.lstatSync;
  fs.lstatSync = (value, options) => value === process.env.RENULUS_DELIVERY_OUTPUT
    ? { isSymbolicLink: () => true } : original(value, options);
}
try {
  const config = require(process.argv[1]);
  process.stdout.write(JSON.stringify({output: config.directories.output, appId: config.appId}));
} catch (error) { process.stderr.write(error.message); process.exitCode = 1; }
"""
        return subprocess.run([shutil.which("node"), "-e", code, str(DESKTOP / "electron-builder.config.cjs"),
                               "junction" if junction else "plain"],
                              env=environment, capture_output=True, text=True, check=False)

    def test_builder_admits_default_and_named_c_root_without_manufacture(self):
        for root in (None, EXTERNAL_DELIVERY_ROOT / "deliveries/relocation-check-never-created"):
            output = (root or EXTERNAL_DELIVERY_ROOT) / "matching-cafe1234/never-created"
            result = self.config(output, root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(Path(json.loads(result.stdout)["output"]), output)
            self.assertFalse(output.exists())

    def test_builder_refuses_e_private_escaped_and_unselected_output(self):
        named = EXTERNAL_DELIVERY_ROOT / "deliveries/relocation-check-never-created"
        cases = [(root / family, None) for root in (EXTERNAL_DELIVERY_ROOT, PUBLIC_INPUT_ROOT)
                 for family in ("repo/private", "data/learning", "profiles/native", "credentials/auth.json")]
        cases += [(PUBLIC_INPUT_ROOT / "matching-cafe1234", None),
                  (EXTERNAL_DELIVERY_ROOT.parent / "desktop-20261005-other/matching-cafe1234", None),
                  (EXTERNAL_DELIVERY_ROOT / "matching-cafe1234", named),
                  (Path("C:/Users/karol/.codex/auth.json"), None)]
        for output, root in cases:
            with self.subTest(output=output, root=root):
                result = self.config(output, root)
                self.assertEqual(result.returncode, 1)
                self.assertIn("delivery output", result.stderr)

    def test_builder_refuses_invalid_root_and_mocked_junction(self):
        output = EXTERNAL_DELIVERY_ROOT / "matching-cafe1234"
        for root in (PUBLIC_INPUT_ROOT, EXTERNAL_DELIVERY_ROOT / "repo",
                     EXTERNAL_DELIVERY_ROOT / "data", EXTERNAL_DELIVERY_ROOT / "credentials",
                     EXTERNAL_DELIVERY_ROOT / "deliveries/nul.txt",
                     EXTERNAL_DELIVERY_ROOT / "deliveries/alias."):
            with self.subTest(root=root):
                result = self.config(output, root)
                self.assertEqual(result.returncode, 1)
                self.assertIn("DeliveryRoot", result.stderr)
        result = self.config(output, junction=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("reparse", result.stderr)


if __name__ == "__main__":
    unittest.main()
