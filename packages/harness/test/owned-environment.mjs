import { mkdtempSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

// Runs before OpenCode imports, whose global path module snapshots XDG roots.
// Deliberately retained under the OS temp root for failed-test diagnostics.
const root = mkdtempSync(path.join(tmpdir(), "renulus-sdk-env-"));
for (const [name, directory] of Object.entries({
  HOME: "home", USERPROFILE: "home", OPENCODE_TEST_HOME: "home",
  APPDATA: "config", LOCALAPPDATA: "local", XDG_CONFIG_HOME: "config",
  XDG_DATA_HOME: "data", XDG_CACHE_HOME: "cache", XDG_STATE_HOME: "state",
  XDG_RUNTIME_DIR: "run", TEMP: "tmp", TMP: "tmp",
})) {
  process.env[name] = path.join(root, directory);
  mkdirSync(process.env[name], { recursive: true });
}
process.env.PATH = path.dirname(process.execPath);
