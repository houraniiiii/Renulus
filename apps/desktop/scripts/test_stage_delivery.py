"""Delivery refusal checks use real synthetic Git commits and owned folders."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

spec = importlib.util.spec_from_file_location("stage_delivery", Path(__file__).with_name("stage-delivery.py"))
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class DeliveryBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_root = delivery.EXTERNAL_DELIVERY_ROOT / "temporary" / ("delivery-tests-" + uuid4().hex)
        cls.test_root.mkdir(parents=True)

    def test_backend_and_renderer_staging_are_confined_to_exact_generated_roots(self):
        target = delivery.EXTERNAL_DELIVERY_ROOT / "source-only-test-not-created"
        self.assertEqual(delivery.generated_path(target, fresh=True), target.resolve())
        self.assertFalse(target.exists())
        for escaped in (target / "../../outside", delivery.EXTERNAL_DELIVERY_ROOT,
                        delivery.EXTERNAL_DELIVERY_ROOT.parent / "desktop-20261005-other/payload"):
            with self.subTest(escaped=escaped), self.assertRaises(ValueError):
                delivery.generated_path(escaped, fresh=True)

    def test_exact_authorised_external_root_accepts_fresh_output_without_writes(self):
        target = delivery.EXTERNAL_DELIVERY_ROOT / "preflight-only-synthetic-fresh"
        self.assertFalse(target.exists())
        self.assertEqual(delivery.delivery_output(target), target.resolve())
        self.assertFalse(target.exists())

    def test_external_sibling_prefix_and_parent_escape_are_rejected(self):
        for target in (delivery.EXTERNAL_DELIVERY_ROOT.parent / "desktop-20261005-other/new",
                       delivery.EXTERNAL_DELIVERY_ROOT / "../outside/new",
                       Path("F:/Renulus-native-delivery/desktop-20261005/new"),
                       delivery.EXTERNAL_DELIVERY_ROOT):
            with self.subTest(target=target), self.assertRaises(ValueError):
                delivery.delivery_output(target)

    def test_external_root_existing_checkpoint_is_preserved(self):
        with tempfile.TemporaryDirectory(dir=self.test_root) as temporary:
            root = Path(temporary)
            target = root / "existing"
            target.mkdir()
            sentinel = target / "installer.exe"
            sentinel.write_bytes(b"synthetic-checkpoint")
            with patch.object(delivery, "EXTERNAL_DELIVERY_ROOT", root):
                with self.assertRaisesRegex(ValueError, "checkpoint"):
                    delivery.delivery_output(target)
            self.assertEqual(sentinel.read_bytes(), b"synthetic-checkpoint")

    def test_existing_checkpoint_and_path_escape_are_rejected_without_changes(self):
        with tempfile.TemporaryDirectory(dir=self.test_root) as temporary:
            root = Path(temporary)
            release, existing = root / "release", root / "release/checkpoint"
            existing.mkdir(parents=True)
            sentinel = existing / "installer.exe"
            sentinel.write_bytes(b"synthetic-preserved-installer")
            with self.assertRaisesRegex(ValueError, "checkpoint"):
                delivery.owned_path(existing, release, fresh=True)
            with self.assertRaisesRegex(ValueError, "assigned"):
                delivery.owned_path(root / "outside", release, fresh=True)
            self.assertEqual(sentinel.read_bytes(), b"synthetic-preserved-installer")
            self.assertFalse((root / "outside").exists())

    def test_moving_branch_name_cannot_identify_a_delivery(self):
        with tempfile.TemporaryDirectory(dir=self.test_root) as temporary:
            with self.assertRaisesRegex(ValueError, "exact 40-character"):
                delivery.committed_revision(Path(temporary), "HEAD")

    def test_changed_wheel_lock_blocks_refresh_before_any_public_payload_mutation(self):
        with tempfile.TemporaryDirectory(dir=self.test_root) as temporary:
            root = Path(temporary)
            repo, payload = root / "source", root / "payload"
            repo.mkdir(); payload.mkdir()
            sentinel = payload / "synthetic-wheel.dll"
            sentinel.write_bytes(b"synthetic-original-wheel")
            subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)
            def commit():
                subprocess.run(["git", "add", "uv.lock"], cwd=repo, check=True)
                subprocess.run(["git", "-c", "user.name=Synthetic test", "-c",
                    "user.email=synthetic@example.invalid", "commit", "--quiet",
                    "-m", "Synthetic locked dependency"], cwd=repo, check=True)
                return delivery.git(repo, "rev-parse", "HEAD").decode().strip()
            (repo / "uv.lock").write_text("synthetic-wheel-v1")
            before = commit()
            self.assertEqual(delivery.committed_revision(repo, before), before)
            (repo / "uv.lock").write_text("synthetic-wheel-v2")
            after = commit()
            with self.assertRaisesRegex(ValueError, "dependency lock changed"):
                delivery.dependency_check(repo, before, after)
            self.assertEqual(sentinel.read_bytes(), b"synthetic-original-wheel")


if __name__ == "__main__":
    unittest.main()
