import { mkdirSync } from "node:fs";
import path from "node:path";

// Set before SDK imports. Only this lane's owned synthetic roots are writable.
const root = "C:/Renulus/scratch/oc-h02-h08/providers/sdk-environment";
for (const [name, directory] of Object.entries({
  OPENCODE_TEST_HOME: "home", APPDATA: "config", LOCALAPPDATA: "local",
  XDG_CONFIG_HOME: "config", XDG_DATA_HOME: "data", XDG_CACHE_HOME: "cache",
  XDG_STATE_HOME: "state", XDG_RUNTIME_DIR: "run", TEMP: "tmp", TMP: "tmp",
})) {
  process.env[name] = path.join(root, directory);
  mkdirSync(process.env[name], { recursive: true });
}
