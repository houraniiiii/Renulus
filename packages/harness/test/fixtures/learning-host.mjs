import { openLearningHarness } from '../../src/learning-host.ts';
import { runHarnessIpc } from '../../src/ipc.ts';
import { scriptedModel } from '../scripted-model.ts';

await runHarnessIpc(async (boot, domain) => {
  const model = await scriptedModel('Synthetic cited CKD explanation [1].', false,
    { name: 'renulus_library_retrieve', input: { query: 'CKD', limit: 1 } });
  const host = await openLearningHarness({ root: boot.root, profileId: boot.profile_id, storeId: boot.store_id,
    domainStoreId: boot.domain_store_id, domainPath: boot.domain_path, model }, domain);
  let settled;
  return { ...host,
    async status() { return { ...await host.status(), modelCalls: await model.count() }; },
    settled() { return settled ??= (async () => { await host.settled(); await model.close(); })(); },
  };
});
