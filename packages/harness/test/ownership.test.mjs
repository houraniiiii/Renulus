import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";
import { execFileSync } from "node:child_process";
import { acquireStore } from "../src/ownership.ts";

test("a store has one owner until the actual owner's release", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-lease-"));
  let owner;
  try {
    owner = await acquireStore(root, "store-1");
    await assert.rejects(acquireStore(root, "store-1"), /store_owned/);
    await owner.release();
    owner = await acquireStore(root, "store-1");
  } finally {
    await owner?.release();
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    assert.ok(path.basename(root).startsWith("renulus-lease-"));
    await rm(root, { recursive: true, force: true });
  }
});

test("a successor can own the store after the previous process has actually died", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-lease-"));
  let owner;
  try {
    const moduleUrl = new URL("../src/ownership.ts", import.meta.url).href;
    execFileSync(process.execPath, ["--input-type=module", "--eval",
      `const {acquireStore}=await import(${JSON.stringify(moduleUrl)}); await acquireStore(process.argv[1], 'store-1');`, root]);
    owner = await acquireStore(root, "store-1");
  } finally {
    await owner?.release();
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    assert.ok(path.basename(root).startsWith("renulus-lease-"));
    await rm(root, { recursive: true, force: true });
  }
});
