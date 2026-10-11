import "./owned-environment.mjs";
import { test } from "node:test";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";

test("actual native owner drains delayed store activation before releasing ownership", async () => {
  await promisify(execFile)(process.execPath, ["--experimental-test-module-mocks",
    fileURLToPath(new URL("./fixtures/activation-drain.mjs", import.meta.url))], { windowsHide: true });
});
