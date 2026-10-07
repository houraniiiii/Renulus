// Compile the actual pinned factory in both modes. No builder build() call: it
// executes its uninstaller generator. This probe never executes any NSIS output.
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const policy = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
assert.match(policy.source_revision, /^[0-9a-f]{40}$/);
const root = path.resolve(policy.root);
const work = path.join(root, "preflight");
fs.mkdirSync(work);
const modules = path.resolve(policy.modules);
const library = path.join(modules, "app-builder-lib");
const load = relative => import(pathToFileURL(path.join(library, relative)).href);
const hash = (file, algorithm = "sha256") => crypto.createHash(algorithm).update(fs.readFileSync(file)).digest("hex");
for (const [relative, expected] of Object.entries(policy.factory.sha256)) assert.equal(hash(path.join(library, relative)), expected, relative);
const { NsisScriptGenerator, nsisEscapeString } = await load("dist/targets/win/nsis/nsisScriptGenerator.js");
const { LangConfigurator, createAddLangsMacro, addCustomMessageFileInclude } = await load("dist/targets/win/nsis/nsisLang.js");
const { compute7zCompressArgs } = await load("dist/targets/archive.js");
const { getCustomToolsetPath } = await load("dist/toolsets/custom.js");
const { getMakeNsisPath } = await load("dist/toolsets/nsis.js");
const { validateConfiguration } = await load("dist/util/config/config.js");
const overrides = JSON.parse(fs.readFileSync(path.join(root, "builder-overrides.json"), "utf8"));
await validateConfiguration({ compression: overrides.compression, toolsets: overrides.toolsets, nsis: overrides.nsis }, { isEnabled: false });
for (const [kind, value] of Object.entries(overrides.toolsets)) {
  assert.equal(path.resolve(await getCustomToolsetPath(value, work)), path.join(root, "toolsets", kind));
}
assert.equal((await getMakeNsisPath(overrides.toolsets.nsis, work)).path, path.join(root, "toolsets/nsis/makensis.cmd"));
const templates = path.join(library, "templates/nsis");
const nsis = path.join(root, "toolsets/nsis/windows");
const compiler = path.join(nsis, "Bin/makensis.exe");
const sevenZip = path.join(root, "toolsets/sevenZip/bin/7za.exe");
const env = { ...process.env, NSISDIR: nsis, TEMP: work, TMP: work, ELECTRON_BUILDER_COMPRESSION_LEVEL: "1" };
delete env.ELECTRON_RUN_AS_NODE;
const receipts = [];
function run(file, args, label, input, expectedExit = 0) {
  const started = performance.now();
  const result = spawnSync(file, args, { cwd: work, env, input, encoding: "utf8", windowsHide: true, timeout: 60000, maxBuffer: 16 * 1024 * 1024 });
  fs.writeFileSync(path.join(work, `${label}.stdout.log`), result.stdout || "");
  fs.writeFileSync(path.join(work, `${label}.stderr.log`), result.stderr || "");
  receipts.push({ label, args, exit: result.status, expected_exit: expectedExit, elapsed_seconds: (performance.now() - started) / 1000 });
  assert.ifError(result.error);
  assert.equal(result.status, expectedExit, `${label} failed: ${result.stderr || result.stdout}`);
  return result;
}
const fixture = path.join(work, "fixture");
fs.mkdirSync(fixture);
const sentinel = "Synthetic public packaging fixture; never an application or patient input.\n";
fs.writeFileSync(path.join(fixture, "sentinel.txt"), sentinel);
const archive = path.join(work, "synthetic.nsis.7z");
const compression = compute7zCompressArgs("7z", { compression: "normal", withoutDir: true, installTimeDecodable: true, dictSize: 1, solid: false, isArchiveHeaderCompressed: false });
assert(compression.includes("-mx=1"));
assert(compression.includes("-mf=BCJ"));
run(sevenZip, [...compression, archive, path.join(fixture, "sentinel.txt")], "synthetic-archive");
const extracted = path.join(work, "extracted");
run(sevenZip, ["x", archive, `-o${extracted}`, "-y"], "synthetic-extract");
assert.equal(fs.readFileSync(path.join(extracted, "sentinel.txt"), "utf8"), sentinel);

const header = new NsisScriptGenerator();
header.include(path.join(templates, "include/StdUtils.nsh"));
header.addIncludeDir(path.join(templates, "include"));
header.flags(["updated", "force-run", "keep-shortcuts", "no-desktop-shortcut", "delete-app-data", "allusers", "currentuser"]);
const languages = new LangConfigurator({});
createAddLangsMacro(header, languages);
let message = 0;
// This context only allocates language files; the production factory generator
// produces their contents. It does not simulate an application or provider.
const messageContext = { getTempFile: async () => path.join(work, `messages-${++message}.nsh`) };
for (const name of ["messages.yml", "assistedMessages.yml"]) await addCustomMessageFileInclude(name, messageContext, header, languages);
header.addPluginDir("x86-unicode", path.join(nsis, "Plugins/x86-unicode"));
header.include(path.join(root, "installer.nsh"));
const script = header.build() + fs.readFileSync(path.join(templates, "installer.nsi"), "utf8");
fs.writeFileSync(path.join(work, "full-factory.nsi"), script);
const defines = {
  APP_ID: `org.renulus.packaging.preflight.${policy.source_revision}`,
  APP_GUID: "71cdd385-9bbf-4b88-8b0e-62fdd85d1675",
  UNINSTALL_APP_KEY: `RenulusPackagingPreflight-${policy.source_revision}`,
  PRODUCT_NAME: "Renulus Packaging Synthetic Preflight", PRODUCT_FILENAME: "Synthetic Renulus",
  APP_FILENAME: "RenulusPackagingSynthetic", APP_DESCRIPTION: "Synthetic packaging compiler evidence only", VERSION: "0.1.0",
  PROJECT_DIR: work, BUILD_RESOURCES_DIR: work, APP_PACKAGE_NAME: "renulus-packaging-synthetic",
  APP_INSTALLER_STORE_FILE: "renulus-packaging-synthetic-updater\\installer.exe",
  APP_64: archive, APP_64_NAME: path.basename(archive), APP_64_HASH: hash(archive, "sha512").toUpperCase(),
  APP_64_UNPACKED_SIZE: "1", COMPRESSION_METHOD: "7z", COMPRESS: "auto",
  INSTALL_MODE_PER_ALL_USERS_REQUIRED: null, HIDE_RUN_AFTER_FINISH: null, allowToChangeInstallationDirectory: null,
  SHORTCUT_NAME: "Renulus packaging synthetic", UNINSTALL_DISPLAY_NAME: "Renulus packaging synthetic",
  DO_NOT_CREATE_DESKTOP_SHORTCUT: null, DO_NOT_CREATE_START_MENU_SHORTCUT: null,
  MUI_WELCOMEFINISHPAGE_BITMAP: "${NSISDIR}\\Contrib\\Graphics\\Wizard\\nsis3-metro.bmp",
  MUI_UNWELCOMEFINISHPAGE_BITMAP: "${NSISDIR}\\Contrib\\Graphics\\Wizard\\nsis3-metro.bmp",
};
const defineArgs = values => Object.entries(values).map(([name, value]) => `-D${name}${value === null ? "" : "=" + nsisEscapeString(value)}`);
for (const mode of ["uninstaller", "installer"]) {
  const output = path.join(work, `${mode}-compile-only.exe`);
  const scoped = { ...defines, UNINSTALLER_OUT_FILE: mode === "installer" ? path.join(work, "synthetic-uninstaller-placeholder.bin") : path.join(work, "uninstaller-never-produced.exe") };
  if (mode === "uninstaller") scoped.BUILD_UNINSTALLER = null;
  // The final compiler only needs bytes at File UNINSTALLER_OUT_FILE. A labelled
  // inert sentinel avoids running the intermediate uninstaller generator.
  if (mode === "installer") fs.writeFileSync(scoped.UNINSTALLER_OUT_FILE, sentinel);
  const commands = ["-WX", "-INPUTCHARSET", "UTF8", ...defineArgs(scoped), `-XOutFile "${output}"`, "-XUnicode true", "-XSetCompressor zlib"];
  if (mode === "uninstaller") {
    // Reproduce the preserved Windows case-insensitive collision with just the
    // generated factory file temporarily absent; keep originals untouched.
    const admitted = path.join(root, "includes/multiUser.nsh");
    const preserved = path.join(work, "multiUser.nsh.preserved");
    fs.renameSync(admitted, preserved);
    try {
      const failure = run(compiler, [...commands, "-DRENULUS_POLICY_PREPROCESS_ONLY", "-PPO", "-"], "stock-collision-refused", script, 1);
      assert((failure.stderr + failure.stdout).includes("MULTIUSER_EXECUTIONLEVEL not set"));
      assert(!fs.existsSync(output));
    } finally {
      fs.renameSync(preserved, admitted);
    }
  }
  run(compiler, [...commands, "-DRENULUS_POLICY_PREPROCESS_ONLY", "-PPO", "-"], `${mode}-preprocess`, script);
  assert(!fs.existsSync(output), "Preprocessing produced an executable");
  run(compiler, [...commands, "-"], `${mode}-compile`, script);
  assert(fs.statSync(output).size > 0);
}
for (const name of ["compiled-factory.log", "compiled-guard.log", "compiled-cache.log"]) {
  const contents = fs.readFileSync(path.join(root, name), "utf8");
  assert(contents.includes(policy.source_revision), `Actual compiler marker missing: ${name}`);
}
const evidence = {
  status: "passed", source_revision: policy.source_revision, factory_root_includes: Object.keys(policy.root_includes),
  factory_preprocess: "both modes passed", factory_compile: "both modes passed with warnings as errors",
  synthetic_archive_round_trip: "passed", compression_args: compression, receipts,
  supported_local_toolsets: "resolved through pinned builder API; configuration schema passed",
  stock_include_collision: "reproduced and refused; admitted factory copy then passed",
  outputs: ["uninstaller", "installer"].map(mode => { const file = path.join(work, `${mode}-compile-only.exe`); return { path: file, bytes: fs.statSync(file).size, sha256: hash(file) }; }),
  installer_execution: false, acceptance: "compiler machinery only; no product manufacture, install, helper, native or provider acceptance",
};
fs.writeFileSync(path.join(root, "preflight-evidence.json"), JSON.stringify(evidence, null, 2));
process.stdout.write(JSON.stringify(evidence) + "\n");
