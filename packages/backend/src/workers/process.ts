// SPDX-License-Identifier: MIT
import { spawn } from "node:child_process";
import { createHash, randomBytes, randomUUID } from "node:crypto";
import { mkdir, mkdtemp, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import document from "../../../contracts/worker.schema.json" with { type: "json" };
import type { BrokerPaths, Capacity, DerivedPaths, HelperPaths, NativePaths, ProcessIdentity, Revisions } from "../../../contracts/worker.ts";
import { decodeWorkerLaunch } from "../contracts/worker-codec.ts";
import { WorkerChannel, type WorkerGenerationHandler } from "./channel.ts";

export const DEFAULT_WORKER_CAPACITY = Object.freeze(Object.fromEntries(Object.entries(document.$defs.Capacity.properties)
  .map(([key, schema]) => [key, schema.default]))) as Readonly<Required<Capacity>>;

async function bounded<A>(promise: Promise<A>, milliseconds: number, code: string) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try { return await Promise.race([promise, new Promise<never>((_, reject) => { timer = setTimeout(() => reject(new Error(code)), milliseconds); })]); }
  finally { clearTimeout(timer); }
}

export interface EngineWorkerOptions {
  python: string;
  sourceRoot: string;
  launchRoot: string;
  identity: ProcessIdentity;
  retention: "saved" | "temporary";
  current: () => Revisions;
  helpers?: HelperPaths;
  derived?: DerivedPaths;
  broker?: BrokerPaths;
  native?: NativePaths;
  generate?: WorkerGenerationHandler;
  capacity?: Partial<Required<Capacity>>;
}

/** A single owned engine process. It never opens canonical repositories. */
export async function openEngineWorker(options: EngineWorkerOptions) {
  for (const value of [options.python, options.sourceRoot, options.launchRoot])
    if (!path.isAbsolute(value) || path.resolve(value) === path.parse(value).root) throw new Error("worker_owned_paths_required");
  await mkdir(options.launchRoot, { recursive: true });
  const root = await mkdtemp(path.join(options.launchRoot, "worker-"));
  const temporary = path.join(root, "temp");
  await mkdir(temporary);
  const configPath = path.join(root, "launch.json");
  const token = randomBytes(32).toString("hex");
  const capacity = { ...DEFAULT_WORKER_CAPACITY, ...options.capacity };
  const config = decodeWorkerLaunch({ protocol: "renulus-worker/1", identity: options.identity,
    revisions: options.current(), retention: options.retention, capacity,
    launch_token_sha256: createHash("sha256").update(token).digest("hex"), helpers: options.helpers ?? null,
    derived: options.derived ?? null, broker: options.broker ?? null, native: options.native ?? null });
  // Metadata only: no token, content, artifact digest or personal configuration.
  await writeFile(configPath, JSON.stringify(config), { flag: "wx", mode: 0o600 });
  const environment: NodeJS.ProcessEnv = {};
  for (const key of ["SystemRoot", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT"])
    if (process.env[key]) environment[key] = process.env[key];
  Object.assign(environment, { PATH: path.dirname(options.python), PYTHONUTF8: "1", PYTHONDONTWRITEBYTECODE: "1",
    PYTHONUNBUFFERED: "1", PYTHONPATH: path.join(options.sourceRoot, "runtime"), TEMP: temporary, TMP: temporary });
  const child = spawn(options.python, ["-B", "-m", "renulus.workers.main", "--config", configPath], {
    cwd: options.sourceRoot, env: environment, windowsHide: true, stdio: ["pipe", "pipe", "ignore"],
  });
  const exit = new Promise<number | null>(resolve => child.once("exit", code => resolve(code)));
  const outputClosed = new Promise<void>(resolve => child.stdout.once("end", () => resolve()));
  let spawnFailure: Error | undefined;
  child.once("error", error => { spawnFailure = error; });
  if (!child.pid) { await unlink(configPath); throw new Error("worker_spawn_failed"); }
  const channel = new WorkerChannel(child.stdout, child.stdin, options.identity, child.pid, capacity,
    options.current, options.retention, options.generate);
  child.once("error", () => channel.disconnect("worker_spawn_failed"));
  let ready;
  try { ready = await bounded(channel.hello(token), 180_000, "worker_handshake_timeout"); }
  catch (error) {
    child.stdin.end();
    try { await bounded(exit, 10_000, "worker_startup_settlement_held"); await unlink(configPath); }
    catch { throw Object.assign(new Error("worker_startup_settlement_held"), { ownedPid: child.pid }); }
    throw spawnFailure ?? error;
  }
  // The one-use authenticator has been consumed. The worker retains immutable
  // parsed config in memory and no longer needs its metadata launch file.
  await unlink(configPath);
  let close: Promise<void> | undefined;
  let shutdown: Promise<void> | undefined;
  let eofSent = false;
  return {
    channel, ready, pid: ready.pid, launcherPid: child.pid,
    close: () => close ??= (async () => {
      shutdown ??= (async () => {
        const binding = { operation_id: "close_" + randomUUID().replaceAll("-", ""), attempt_id: "attempt_1" };
        const call = channel.submit("worker.settle", { action: "close", target: null, revisions: null, artifact_handle: null }, binding);
        const acknowledgement = await call.admission;
        if (!["accepted_pending", "committed_reference"].includes(acknowledgement.reply.outcome)) throw new Error("worker_close_refused");
        channel.release(call.requestId);
        await channel.drain();
        // Retain shutdown progress across observer timeouts. Late actual engine
        // settlement can complete this same shutdown; no second close or EOF.
        if (!eofSent) { eofSent = true; child.stdin.end(); }
      })();
      // Physical exit and drained stdout prove actual closure. The 30s bound is
      // an observation limit; supported engine work may retain its lease for 120s.
      const [code] = await bounded(Promise.all([shutdown.then(() => exit), outputClosed]), 30_000, "worker_settlement_held");
      if (code !== 0) throw new Error("worker_exit_uncertain");
    })().catch(error => { close = undefined; throw error; }),
  };
}
