// Real saved native host/private IPC. Only model inference and observation delay
// are synthetic; persisted native messages and canonical publication are untouched.
import { access, mkdir, unlink, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { setTimeout } from 'node:timers/promises';

// ManagedHarnessProcess intentionally strips inherited environment variables.
// This explicit fixture setting is carried in the trusted boot descriptor.
const source = JSON.parse(process.env.RENULUS_HARNESS_BOOT).synthetic_source_root
  ?? fileURLToPath(new URL('../../../../', import.meta.url));
const moduleAt = relative => import(pathToFileURL(path.join(source, relative)).href);
const { openLearningHarness } = await moduleAt('packages/harness/src/learning-host.ts');
const { runHarnessIpc } = await moduleAt('packages/harness/src/ipc.ts');
const { scriptedModel } = await moduleAt('packages/harness/test/scripted-model.ts');

async function exists(file) {
  try { await access(file); return true; }
  catch (error) { if (error.code === 'ENOENT') return false; throw error; }
}

await runHarnessIpc(async (boot, domain) => {
  if (typeof boot.synthetic_answer !== 'string' || !boot.synthetic_answer.trim()) {
    throw new Error('synthetic_answer_required');
  }
  const model = await scriptedModel(boot.synthetic_answer);
  const host = await openLearningHarness({ root: boot.root, profileId: boot.profile_id,
    storeId: boot.store_id, domainStoreId: boot.domain_store_id, domainPath: boot.domain_path, model }, domain);
  const probe = path.join(boot.root, 'cache', 'learning-extraction');
  await mkdir(probe, { recursive: true });
  let heldReads = 0;
  let settlement;
  return { ...host,
    async observe(...arguments_) {
      const hold = path.join(probe, 'read-hold');
      if (await exists(hold)) {
        await unlink(hold); // One observation owns the gate.
        heldReads += 1;
        try {
          await writeFile(path.join(probe, 'read-entered'), 'owned-native-observation');
          const deadline = Date.now() + 15000;
          while (!await exists(path.join(probe, 'read-release'))) {
            if (Date.now() >= deadline) throw new Error('synthetic_read_gate_timeout');
            await setTimeout(10);
          }
        } finally { heldReads -= 1; }
      }
      return host.observe(...arguments_);
    },
    async status() {
      return { ...await host.status(), heldReads, modelCalls: await model.count() };
    },
    settled() {
      return settlement ??= (async () => {
        await writeFile(path.join(probe, 'read-release'), 'shutdown');
        await host.settled();
        await model.close();
      })();
    },
  };
});
