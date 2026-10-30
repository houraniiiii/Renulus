// SPDX-License-Identifier: MIT
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import path from "node:path";

export interface PythonDomainOptions {
  readonly python: string;
  readonly sourceRoot: string;
  readonly profile: string;
  readonly token: string;
  readonly desktopHarness: boolean;
}

const PROTOCOL = "renulus-domain/1";
const FRAME_BYTES = 16_384;

async function bounded<A>(promise: Promise<A>, milliseconds: number, code: string): Promise<A> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([promise, new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error(code)), milliseconds);
    })]);
  } finally { clearTimeout(timer); }
}

function environment(options: PythonDomainOptions) {
  const env: NodeJS.ProcessEnv = {};
  for (const key of ["SystemRoot", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LOCALAPPDATA", "APPDATA",
    "USERPROFILE", "COMSPEC", "PATHEXT"]) if (process.env[key]) env[key] = process.env[key];
  return { ...env, PATH: path.dirname(options.python), PYTHONUTF8: "1", PYTHONDONTWRITEBYTECODE: "1",
    PYTHONUNBUFFERED: "1", PYTHONPATH: [path.join(options.sourceRoot, "runtime"), path.join(options.sourceRoot, "upstream", "hermes")].join(path.delimiter),
    HERMES_HOME: path.join(options.profile, "hermes") };
}

function exact(value: unknown, keys: string[]): value is Record<string, any> {
  return !!value && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).sort().join(",") === keys.sort().join(",");
}

/** Migration-only owner. Readiness and settlement come exclusively from inherited
 * pipes, never from an unauthenticated port probe or process death.
 */
export async function openPythonDomain(options: PythonDomainOptions) {
  for (const value of [options.python, options.sourceRoot, options.profile])
    if (!path.isAbsolute(value) || path.resolve(value) === path.parse(value).root) throw new Error("explicit_owned_paths_required");
  if (!existsSync(options.python) || !existsSync(path.join(options.sourceRoot, "runtime", "renulus", "runtime", "domain_process.py")) ||
      !options.token || Buffer.byteLength(options.token) > 4096) throw new Error("python_domain_inputs_missing");
  const profile = path.resolve(options.profile), nonce = randomUUID();
  const child = spawn(options.python, ["-B", "-m", "renulus.runtime.domain_process", "--profile", profile,
    "--source-root", options.sourceRoot, "--launch-nonce", nonce, ...(options.desktopHarness ? ["--desktop-harness"] : [])], {
    cwd: options.sourceRoot, env: environment(options), windowsHide: true, stdio: ["pipe", "pipe", "ignore"],
  });
  let exit: { code: number | null; signal: NodeJS.Signals | null } | undefined;
  const exited = new Promise<void>(resolve => child.once("exit", (code, signal) => { exit = { code, signal }; resolve(); }));
  // close follows exit AND closure of inherited stdio, including stdout held by
  // the actual Python process behind a Windows venv launcher.
  const closed = new Promise<void>(resolve => child.once("close", () => resolve()));
  let lost: Error | undefined, acknowledged = false;
  let signalLoss!: (error: Error) => void;
  const loss = new Promise<Error>(resolve => { signalLoss = resolve; });
  let ready: { port: number; pid: number; process: Record<string, any> } | undefined;
  let acceptReady!: () => void, rejectReady!: (error: Error) => void;
  const readiness = new Promise<void>((resolve, reject) => { acceptReady = resolve; rejectReady = reject; });
  let pending: { id: string; resolve: () => void; reject: (error: Error) => void } | undefined;
  const fail = (code: string) => {
    if (!lost) { lost = new Error(code); signalLoss(lost); }
    rejectReady(lost);
    pending?.reject(lost);
    pending = undefined;
    // Losing control revokes this connection. EOF asks a surviving actual child
    // to drain; it does not turn an unacknowledged exit into success.
    child.stdin.end();
  };
  child.once("error", () => fail("python_domain_spawn_failed"));
  child.stdin.on("error", () => fail("python_domain_control_lost"));
  child.stdout.on("error", () => fail("python_domain_control_lost"));
  // exit can precede delivery of buffered stdout. Let the pipe drain before
  // deciding that the child died without a matching terminal acknowledgement.
  child.once("close", () => { if (!acknowledged) fail("python_domain_exit_uncertain"); });
  child.stdout.once("end", () => {
    if (buffer.length) fail("python_domain_invalid_control");
    else if (!acknowledged) fail("python_domain_control_lost");
  });
  let buffer = Buffer.alloc(0);
  child.stdout.on("data", (chunk: Buffer) => {
    if (lost) return;
    buffer = Buffer.concat([buffer, chunk]);
    while (!lost) {
      const end = buffer.indexOf(10);
      if (end < 0) { if (buffer.length >= FRAME_BYTES) fail("python_domain_invalid_control"); return; }
      if (end + 1 > FRAME_BYTES) { fail("python_domain_invalid_control"); return; }
      const line = buffer.subarray(0, end);
      buffer = buffer.subarray(end + 1);
      try {
        const frame: unknown = JSON.parse(line.toString("utf8"));
        if (!ready) {
          if (!exact(frame, ["protocol", "kind", "profile", "launch_nonce", "pid", "process", "port"]) ||
              frame.protocol !== PROTOCOL || frame.kind !== "ready" || frame.profile !== profile || frame.launch_nonce !== nonce ||
              !Number.isSafeInteger(frame.port) || frame.port < 1 || frame.port > 65535 ||
              !Number.isSafeInteger(frame.pid) || frame.pid < 1 || frame.pid > 0xFFFFFFFF ||
              !exact(frame.process, ["launcher_pid", "actual_pid", "launcher_creation_filetime", "actual_creation_filetime", "ancestry_depth"]) ||
              frame.process.launcher_pid !== child.pid || frame.process.actual_pid !== frame.pid ||
              !Number.isSafeInteger(frame.process.ancestry_depth) || frame.process.ancestry_depth < 0 || frame.process.ancestry_depth > 16 ||
              (frame.pid === child.pid ? frame.process.ancestry_depth !== 0 : frame.process.ancestry_depth < 1) ||
              typeof frame.process.launcher_creation_filetime !== "string" || typeof frame.process.actual_creation_filetime !== "string" ||
              !/^[0-9]{1,20}$/.test(frame.process.launcher_creation_filetime) || !/^[0-9]{1,20}$/.test(frame.process.actual_creation_filetime) ||
              BigInt(frame.process.launcher_creation_filetime) <= 0n ||
              BigInt(frame.process.actual_creation_filetime) < BigInt(frame.process.launcher_creation_filetime)) throw new Error();
          ready = { port: frame.port, pid: frame.pid, process: frame.process };
          acceptReady();
        } else {
          if (!pending || !exact(frame, ["protocol", "kind", "profile", "launch_nonce", "pid", "request_id", "state"]) ||
              frame.protocol !== PROTOCOL || frame.kind !== "shutdown" || frame.profile !== profile ||
              frame.launch_nonce !== nonce || frame.pid !== ready.pid || frame.request_id !== pending.id ||
              !["held", "settled"].includes(frame.state)) throw new Error();
          const call = pending; pending = undefined;
          if (frame.state === "settled") { acknowledged = true; call.resolve(); }
          else call.reject(new Error("python_domain_not_settled"));
        }
      } catch { fail("python_domain_invalid_control"); }
    }
  });
  const send = (frame: object) => child.stdin.write(JSON.stringify(frame) + "\n");
  if (!child.pid) fail("python_domain_spawn_failed");
  else send({ protocol: PROTOCOL, kind: "hello", profile, launch_nonce: nonce,
    expected_launcher_pid: child.pid, token: options.token });

  let closing: Promise<void> | undefined;
  let shutdownReply: Promise<void> | undefined;
  const close = () => closing ??= (async () => {
    if (lost) throw lost;
    if (!ready) throw new Error("python_domain_not_ready");
    if (!acknowledged) {
      // A timed-out observation retains the SAME pending request. Retry observes
      // its eventual reply rather than issuing overlapping shutdowns.
      if (!pending) {
        const id = randomUUID();
        shutdownReply = new Promise<void>((resolve, reject) => { pending = { id, resolve, reject }; });
        send({ protocol: PROTOCOL, kind: "shutdown", profile, launch_nonce: nonce, pid: ready.pid,
          request_id: id, timeout_seconds: 30 });
      }
      await bounded(shutdownReply!, 35_000, "python_domain_settlement_held");
    }
    child.stdin.end();
    await bounded(Promise.all([exited, closed]), 35_000, "python_domain_exit_held");
    if (lost || exit?.code !== 0 || exit.signal !== null) throw lost ?? new Error("python_domain_exit_uncertain");
  })().catch(error => {
    closing = undefined;
    throw Object.assign(error, { ownedPid: ready?.pid ?? child.pid, launcherPid: child.pid,
      settlement: acknowledged ? "acknowledged" : error.message === "python_domain_not_settled" ? "held" : "uncertain" });
  });
  try {
    await bounded(readiness, 300_000, "python_domain_startup_timeout");
    if (lost) throw lost;
  }
  catch (error) {
    // EOF requests the same Services drain even before readiness. Retain identity
    // and retryable exit observation if the startup owner stays held.
    child.stdin.end();
    const drain = () => bounded(closed, 35_000, "python_domain_startup_held");
    try { await drain(); }
    catch { throw Object.assign(new Error("python_domain_startup_held"), {
      ownedPid: child.pid, waitForExit: drain, settlement: "uncertain", cause: error,
    }); }
    throw error;
  }
  return { port: ready!.port, pid: ready!.pid, launcherPid: child.pid!, ready: ready!, loss, close };
}
