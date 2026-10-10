import path from "node:path";
import { randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, rmdirSync, unlinkSync, writeFileSync } from "node:fs";

/** The lease outlives any bounded shutdown observer. Only the settled host releases it. */
export async function acquireStore(root: string, storeId: string) {
  mkdirSync(root, { recursive: true });
  const file = path.join(root, "owner.json");
  const guard = path.join(root, "ownership-guard");
  const token = randomUUID();
  // Every acquisition/release serializes the stale-owner check and replacement.
  // A crash in this tiny filesystem section leaves a fail-closed guard requiring
  // explicit recovery. Age or timeout alone never proves a process has died.
  function exclusive(action: () => void) {
    try { mkdirSync(guard); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code === "EEXIST") throw new Error("store_guard_uncertain");
      throw error;
    }
    try { action(); } finally { rmdirSync(guard); }
  }
  exclusive(() => {
    if (existsSync(file)) {
      const prior = JSON.parse(readFileSync(file, "utf8"));
      if (prior.storeId !== storeId || !Number.isSafeInteger(prior.pid) || prior.pid < 1
          || typeof prior.token !== "string") throw new Error("store_identity_uncertain");
      try { process.kill(prior.pid, 0); throw new Error("store_owned"); }
      catch (error) {
        if ((error as NodeJS.ErrnoException).code !== "ESRCH") throw error;
      }
      unlinkSync(file);
    }
    writeFileSync(file, JSON.stringify({ storeId, pid: process.pid, token }), { flag: "wx" });
  });
  let released = false;
  return {
    async release() {
      if (released) return;
      exclusive(() => {
        if (JSON.parse(readFileSync(file, "utf8")).token !== token) throw new Error("store_ownership_changed");
        unlinkSync(file);
      });
      released = true;
    },
  };
}
