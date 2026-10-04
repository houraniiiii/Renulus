"""Build a committed desktop snapshot without writing another lane's files."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

DESKTOP = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--revision", default="HEAD")
parser.add_argument("--target", type=Path, required=True)
parser.add_argument("--include-native", action="store_true",
                    help="Compile the integrated native entry with this lane's packaged backend adoption")
args = parser.parse_args()
source, target = args.source.resolve(), args.target.resolve()
if not target.is_relative_to(DESKTOP / "test-results") or target.exists():
    raise ValueError("Use a fresh scratch target within this desktop lane test-results")
revision = subprocess.check_output(["git", "rev-parse", args.revision], cwd=source, text=True).strip()
target.mkdir(parents=True)
archive = target / "desktop-source.tar"
subprocess.run(["git", "archive", "--format=tar", "--output", str(archive), revision,
                "--", "apps/desktop"], cwd=source, check=True)
with tarfile.open(archive) as contents:
    contents.extractall(target, filter="data")
snapshot = target / "apps/desktop"
native_adoption = None
if args.include_native:
    backend = snapshot / "electron/backend.ts"
    original = backend.read_bytes()
    adopted = (DESKTOP / "electron/backend.ts").read_bytes()
    native_adoption = {"path": "apps/desktop/electron/backend.ts",
                       "source_sha256": hashlib.sha256(original).hexdigest(),
                       "adopted_sha256": hashlib.sha256(adopted).hexdigest()}
    patch = "".join(difflib.unified_diff(original.decode("utf-8").splitlines(keepends=True),
                  adopted.decode("utf-8").splitlines(keepends=True),
                  fromfile="a/apps/desktop/electron/backend.ts",
                  tofile="b/apps/desktop/electron/backend.ts"))
    backend.write_bytes(adopted)
node = shutil.which("node")
if not node:
    raise ValueError("Developer build tooling requires Node; the portable app does not")
subprocess.run([node, str(DESKTOP / "node_modules/typescript/bin/tsc"), "--noEmit"],
               cwd=snapshot, check=True)
subprocess.run([node, str(DESKTOP / "node_modules/vite/bin/vite.js"), "build"],
               cwd=snapshot, check=True)
manifest = {"version": 1, "source_revision": revision,
            "kind": "committed-integrated-renderer", "typecheck": "passed",
            "build": "passed"}
(snapshot / "dist/renderer-provenance.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
if args.include_native:
    source_pin = json.loads((snapshot / "package.json").read_text())["devDependencies"]["electron"]
    installed_pin = json.loads((DESKTOP / "node_modules/electron/package.json").read_text())["version"]
    if source_pin != installed_pin:
        raise ValueError("The integrated native Electron pin differs from this lane's installed artifact")
    subprocess.run([node, str(snapshot / "scripts/build-electron.mjs")], cwd=snapshot, check=True)
    native = snapshot / "dist-electron"
    native_manifest = {**manifest, "kind": "committed-integrated-native",
                       "electron_version": installed_pin, "backend_adoption": native_adoption,
                       "main_source_sha256": hashlib.sha256((snapshot / "electron/main.ts").read_bytes()).hexdigest(),
                       "profile_source_sha256": hashlib.sha256((snapshot / "electron/profile.ts").read_bytes()).hexdigest(),
                       "main_bundle_sha256": hashlib.sha256((native / "main.cjs").read_bytes()).hexdigest()}
    (native / "native-provenance.json").write_text(json.dumps(native_manifest, indent=2), encoding="utf-8")
    (native / "backend-adoption.patch").write_text(patch, encoding="utf-8")
print(json.dumps({"renderer": str(snapshot / "dist"), **manifest}, indent=2))
