"""Scoped, offline NSIS policy and full factory preflight; never run installers.

Factory copies retain electron-builder MIT attribution. Only the cache copy
macro is patched. The seven factory root includes stay byte-identical and take
compile-directory precedence over NSIS stock MultiUser.nsh on Windows.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile

from delivery_paths import generated_path, public_input_path

BUILDER_VERSION = "27.0.0-alpha.6"
ARCHIVES = {
    "nsis": ("nsis@1.2.1/nsis-bundle-3.12.tar.gz", "56997fdefe25e7928a1a68b4583d08b240b66cf660234053b20131a74cc082f4"),
    "sevenZip": ("7zip@1.0.0/7zip-win-x64.tar.gz", "be071f15bd6da2f78fe81c6ddef2009b0c4d8a51f36b780cb806c7e6df95e1b3"),
}
FACTORY_SHA256 = {
    "templates/nsis/assistedInstaller.nsh": "8aa1230e9717b428664d613fcc5c6a060883410b34cb7853b517fe11b4ee0a76",
    "templates/nsis/common.nsh": "281e8071663d2ef3e9f00bb27e6ef09d2c2b52b85458da07082f2b186100e259",
    "templates/nsis/installSection.nsh": "f45a19cda4d5277629dd83e45891d282d96b4eddd87d363c315d8b7bae51aa51",
    "templates/nsis/multiUser.nsh": "9aca256695c289ec8a875143101fae8c6236bc8c6a7cf369bbe8b4986e09c9cb",
    "templates/nsis/multiUserUi.nsh": "f7a4524244e68dc0782a759e076e5e55fadef0f22bbccf33100a4ab59d69c066",
    "templates/nsis/oneClick.nsh": "87d6c095f37716759c8d9373dcab906394546007abb626c04e1c784158f6de5b",
    "templates/nsis/uninstaller.nsh": "9ee2dac4593478083e8aa6f8487287ce9401006ccd50ecc538871d133ea4a42c",
    "templates/nsis/installer.nsi": "8811964416d122612c3e7601728af5d3f998d677918df829a4e8b4c739c8b9f8",
    "templates/nsis/include/installUtil.nsh": "97bd546b5cd2aaf16b77bc9e2be8a18962dd74ab5c4d23b35b163ca89bf4dd2a",
    "templates/nsis/include/allowOnlyOneInstallerInstance.nsh": "0d4ae12cf0bd177cb85cb77680add3135108ddd21ab5730426e4600e2aaad18f",
    "templates/nsis/include/extractAppPackage.nsh": "e4174388a0f7a1df0b85a0742aa1ea7a4b2b18f9f29dccd6ef10a66212f68148",
    "templates/nsis/include/FileAssociation.nsh": "3680cc9c9d3adee599aed200e0a7b3a7f3b08114ca0b9fbd7a09d7db6726aa73",
    "templates/nsis/include/getProcessInfo.nsh": "1aa6bd7afc8b82534c26c878d2716fd12b7e215b11e2d5becd0d605085b88590",
    "templates/nsis/include/installer.nsh": "0e319437dd01dcbf911f3f48f664fde0cefbaef704f1cdb1739f63d563f5d4a0",
    "templates/nsis/include/nsProcess.nsh": "c8057c110908425e03bca6a4a96fab853a4705844fb5fb6123e7191ce94d0e63",
    "templates/nsis/include/StdUtils.nsh": "e68d1bf7e4afd258b601346b833bf064285213d8f481caa900a1430cdabee275",
    "templates/nsis/include/StrContains.nsh": "5050b692d091915c9f1083b558918c77b90f20683cb1b9e746890d61a79d550b",
    "templates/nsis/include/UAC.nsh": "abd701f2898f987041baa9d7ece9d0f8ee806eb5f7d85a4f39b6c60b8d638769",
    "templates/nsis/include/webPackage.nsh": "2c0c0ab1ce525caf6ef908502d3ec007430986c3022c3987ccfaf021ddabe7b1",
    "templates/nsis/messages.yml": "32620e600b2fbb13449ac9e6e63b3b2bc34b5ab9fb0ccef9577d59332474eaf7",
    "templates/nsis/assistedMessages.yml": "996123f3969810560731af927dc1cfe8fbac6b7f227e9ee4106289f592ce0c06",
    "dist/targets/archive.js": "145e478efcd747842ab2d0e064df0562a878891302d6b91176f6373160189d85",
    "dist/targets/win/nsis/NsisTarget.js": "5757724a5415e8d12dc81f5f17981c9381b493f597f73e6033bf05f75357c40f",
    "dist/targets/win/nsis/nsisLang.js": "f549ab32c22ff9696d05b014838c507dfab0092c42ef50b2e8080e79ef096aa5",
    "dist/targets/win/nsis/nsisScriptGenerator.js": "d58d28f60aa780854f08c8a9513622799df25d91be1ab512ebd58e01b23f0d80",
    "dist/toolsets/custom.js": "93049d5c90d66dce81e2bee855de792cd15a6f20a1295e1e4840772200bb51bb",
    "dist/toolsets/nsis.js": "6c0b0589e204b7122788620dcaed1516ba30da7a4ade6e2611a6e470cb37f32e",
    "dist/toolsets/7zip.js": "ac2117e5e65cb7c2ce2eabfbb180429a5c250eecc6611a57afd89de7acae9834",
    "dist/util/config/config.js": "72b9bf4e22019031fd3494a00218f404b1ee0edae0477c4276e50f0e09b30fb2",
    "scheme.json": "4543677bf0f1981d00782f09364d8340f9c433caa0f201aa64e82b9140f0610f",
}
ROOT_INCLUDES = tuple(Path(name).name for name in FACTORY_SHA256
                      if Path(name).parent.as_posix() == "templates/nsis" and name.endswith(".nsh"))


def digest(file: Path) -> str:
    with file.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def nsis_path(path: Path) -> str:
    # Paths are generated public names, never arbitrary NSIS source fragments.
    value = str(path.absolute())
    if any(c in value for c in ("$", "`", '"', "\n", "\r")):
        raise ValueError("An NSIS generated path contains source-control characters")
    return value


def verify_factory(modules: Path) -> dict:
    modules = public_input_path(modules)
    builder = modules / "app-builder-lib"
    for name in ("app-builder-lib", "electron-builder"):
        metadata = json.loads((modules / name / "package.json").read_text(encoding="utf-8"))
        if metadata.get("version") != BUILDER_VERSION or metadata.get("license") != "MIT":
            raise ValueError("Packaging requires the pinned public MIT builder: " + name)
    root_files = {p.name for p in (builder / "templates/nsis").glob("*.nsh")}
    if root_files != set(ROOT_INCLUDES):
        raise ValueError("The factory root include set changed; review it before packaging")
    for name, expected in FACTORY_SHA256.items():
        file = public_input_path(builder / name)
        if digest(file) != expected:
            raise ValueError("Pinned factory bytes changed: " + name)
    return {"version": BUILDER_VERSION, "sha256": FACTORY_SHA256,
            "licence": "MIT; Copyright (c) 2015 Loopline Systems"}


def verify_archives(cache: Path) -> dict:
    cache = public_input_path(cache)
    for _, (name, expected) in ARCHIVES.items():
        if digest(public_input_path(cache / name)) != expected:
            raise ValueError("The public toolset archive differs from its pin: " + name)
    return {kind: {"archive": str(cache / name), "sha256": expected}
            for kind, (name, expected) in ARCHIVES.items()}


def extract_toolset(archive: Path, target: Path) -> dict:
    """Extract only pinned regular files; compare every destination byte to tar.

    Do not trust stale cache directories or downloader completion timestamps.
    The two selected archives contain only directories and regular files.
    """
    target = generated_path(target, fresh=True)
    records, members, names = [], [], set()
    with tarfile.open(archive, "r:gz") as contents:
        for member in contents.getmembers():
            parts = PurePosixPath(member.name).parts
            if not parts or any(p in ("..", ".") or ":" in p or "\\" in p for p in parts) or member.name.startswith("/"):
                raise ValueError("Toolset archive contains an unsafe path")
            if not (member.isfile() or member.isdir()):
                raise ValueError("Toolset archive contains a link or special entry")
            relative = PurePosixPath(*parts[1:])
            key = relative.as_posix().casefold()
            if key in names:
                raise ValueError("Toolset archive contains a duplicate Windows path")
            names.add(key)
            if len(parts) == 1:
                if not member.isdir():
                    raise ValueError("Toolset archive root must be a directory")
                continue
            members.append((member, relative))
        target.mkdir(parents=True)
        for member, relative in members:
            file = target / relative
            if member.isdir():
                file.mkdir(parents=True, exist_ok=True)
                continue
            file.parent.mkdir(parents=True, exist_ok=True)
            with contents.extractfile(member) as source, file.open("xb") as output:
                hasher = hashlib.sha256()
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    hasher.update(chunk)
                    output.write(chunk)
            expected = hasher.hexdigest()
            if file.stat().st_size != member.size or digest(file) != expected:
                raise ValueError("Copied public toolset changed: " + str(relative))
            records.append({"path": relative.as_posix(), "size": member.size, "sha256": expected})
    return {"files": sorted(records, key=lambda item: item["path"]), "root": str(target)}


def cache_macro(original: str, root: Path, revision: str) -> str:
    # Fail closed if the pinned macro changes; retain all surrounding factory code.
    before = """!macro copyFile FROM TO
  ${StdUtils.GetParentPath} $R5 `${TO}`
  CreateDirectory `$R5`
  ClearErrors
  CopyFiles /SILENT `${FROM}` `${TO}`
!macroend"""
    if original.count(before) != 1:
        raise ValueError("Pinned copyFile macro does not match the reviewed adaptation")
    cache = nsis_path(root / "installer-cache")
    marker = nsis_path(root / "compiled-cache.log")
    after = r'''!macro copyFile FROM TO
  !if "${TO}" == "$LOCALAPPDATA\${APP_INSTALLER_STORE_FILE}"
    !if "${FROM}" != "$EXEPATH"
      !error "Renulus cache copy requires the current public installer"
    !endif
    !ifndef RENULUS_POLICY_PREPROCESS_ONLY
      !appendfile "@MARKER@" "@REVISION@ isolated public installer cache;$\n"
    !endif
    StrCpy $R5 "@CACHE@"
    CreateDirectory "$R5"
    ClearErrors
    CopyFiles /SILENT "${FROM}" "$R5\installer.exe"
    ${if} ${errors}
      SetErrorLevel 14
      Quit
    ${endif}
  !else
    ${StdUtils.GetParentPath} $R5 `${TO}`
    CreateDirectory `$R5`
    ClearErrors
    CopyFiles /SILENT `${FROM}` `${TO}`
  !endif
!macroend'''
    return original.replace(before, after.replace("@MARKER@", marker).replace("@REVISION@", revision).replace("@CACHE@", cache))


def prepare(modules: Path, cache: Path, root: Path, revision: str, install: Path) -> dict:
    if not re.fullmatch("[0-9a-f]{40}", revision):
        raise ValueError("NSIS policy requires an exact revision")
    root = generated_path(root, fresh=True)
    install = generated_path(install, fresh=True)
    modules = public_input_path(modules)
    factory, archives = verify_factory(modules), verify_archives(cache)
    root.mkdir(parents=True)
    receipts = {kind: extract_toolset(Path(value["archive"]), root / "toolsets" / kind)
                for kind, value in archives.items()}
    templates = modules / "app-builder-lib/templates/nsis"
    includes = root / "includes"
    includes.mkdir()
    for name in ROOT_INCLUDES:
        shutil.copyfile(templates / name, includes / name)
        if digest(includes / name) != FACTORY_SHA256["templates/nsis/" + name]:
            raise ValueError("The compile-local factory include changed: " + name)
    original = (templates / "include/installUtil.nsh").read_text(encoding="utf-8")
    adapted = cache_macro(original, root, revision)
    (includes / "installUtil.nsh").write_text(adapted, encoding="utf-8", newline="\n")
    patch = "".join(difflib.unified_diff(original.splitlines(keepends=True), adapted.splitlines(keepends=True),
                                       fromfile="pinned-builder/installUtil.nsh", tofile="generated-policy/installUtil.nsh"))
    (root / "installUtil.patch").write_text(patch, encoding="utf-8")
    header = r'''; Generated Renulus manufacturing policy; factory root files retain MIT.
!addincludedir "@TEMPLATES@"
!cd "@INCLUDES@"
!macro customHeader
  !ifmacrondef initMultiUser
    !error "Renulus requires factory multiUser.nsh, not stock NSIS MultiUser.nsh"
  !endif
  !ifndef RENULUS_POLICY_PREPROCESS_ONLY
    !appendfile "@ROOT@\compiled-factory.log" "@REVISION@ factory initMultiUser admitted;$\n"
  !endif
!macroend
!macro customCheckAppRunning
  !ifndef RENULUS_POLICY_PREPROCESS_ONLY
    !appendfile "@ROOT@\compiled-guard.log" "@REVISION@ exact fresh install guard; no process discovery or closure;$\n"
  !endif
  StrCmp "$INSTDIR" "@INSTALL@" +3 0
  SetErrorLevel 13
  Quit
!macroend
'''
    for token, path in (("@TEMPLATES@", templates), ("@INCLUDES@", includes), ("@ROOT@", root), ("@INSTALL@", install)):
        header = header.replace(token, nsis_path(path))
    (root / "installer.nsh").write_text(header.replace("@REVISION@", revision), encoding="utf-8")
    licences = root / "licences"
    licences.mkdir()
    shutil.copyfile(Path(__file__).with_name("restage-builder-MIT.txt"), licences / "electron-builder-MIT.txt")
    shutil.copyfile(root / "toolsets/nsis/LICENSE", licences / "NSIS-LICENSE.txt")
    shutil.copyfile(root / "toolsets/sevenZip/LICENSE.txt", licences / "7zip-LICENSE.txt")
    shutil.copyfile(root / "toolsets/sevenZip/COPYING", licences / "7zip-COPYING.txt")
    result = {"version": 1, "source_revision": revision, "root": str(root), "modules": str(modules),
              "install": str(install), "factory": factory, "archives": archives, "toolsets": receipts,
              "root_includes": {name: digest(includes / name) for name in ROOT_INCLUDES},
              "header_sha256": digest(root / "installer.nsh"), "adapted_sha256": digest(includes / "installUtil.nsh"),
              "patch_sha256": digest(root / "installUtil.patch"),
              "preflight": "pending full factory preprocess and compile; never execute outputs",
              "compression_level": "1", "installer_execution": False}
    (root / "policy-provenance.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (root / "builder-overrides.json").write_text(json.dumps(builder_overrides(result), indent=2), encoding="utf-8")
    return result


def builder_overrides(policy: dict) -> dict:
    root = Path(policy["root"])
    return {"compression": "normal",
            "toolsets": {kind: {"url": "file://" + str(root / "toolsets" / kind),
                                  "version": "1.2.1" if kind == "nsis" else "1.0.0"}
                         for kind in ARCHIVES},
            "nsis": {"include": str(root / "installer.nsh")},
            "licences": str(root / "licences")}


def preflight(policy: dict, environment: dict | None = None) -> dict:
    root = Path(policy["root"])
    command = [shutil.which("node") or "node", str(Path(__file__).with_name("restage-nsis-preflight.mjs")),
               str(root / "policy-provenance.json")]
    environment = dict(os.environ if environment is None else environment, ELECTRON_BUILDER_COMPRESSION_LEVEL="1")
    environment.pop("ELECTRON_RUN_AS_NODE", None)
    with (root / "preflight.stdout.log").open("w", encoding="utf-8") as stdout, (root / "preflight.stderr.log").open("w", encoding="utf-8") as stderr:
        subprocess.run(command, env=environment, stdout=stdout, stderr=stderr, check=True)
    evidence = json.loads((root / "preflight-evidence.json").read_text(encoding="utf-8"))
    if evidence.get("status") != "passed" or evidence.get("source_revision") != policy["source_revision"] or evidence.get("installer_execution") is not False:
        raise ValueError("Full factory preflight did not establish the requested policy")
    # Preserve fixture markers separately. Manufacture must create its own.
    for name in ("compiled-factory.log", "compiled-guard.log", "compiled-cache.log"):
        (root / name).rename(root / "preflight" / name)
    return evidence


def verify_compiler_markers(policy: dict) -> None:
    for name in ("compiled-factory.log", "compiled-guard.log", "compiled-cache.log"):
        file = Path(policy["root"]) / name
        if not file.is_file() or policy["source_revision"] not in file.read_text():
            raise ValueError("Actual manufacture compiler receipt is missing: " + name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("node-modules", "cache", "target", "install"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    policy = prepare(args.node_modules, args.cache, args.target, args.revision, args.install)
    evidence = preflight(policy)
    print(json.dumps({"policy": policy["root"], "status": evidence["status"],
                      "evidence": str(Path(policy["root"]) / "preflight-evidence.json"),
                      "installer_execution": False}, indent=2))


if __name__ == "__main__":
    main()
