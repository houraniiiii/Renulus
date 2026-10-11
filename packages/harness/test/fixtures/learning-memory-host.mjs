import { openLearningHarness } from '../../src/learning-host.ts';
import { runHarnessIpc } from '../../src/ipc.ts';
import { describeNativeContext } from '../../src/native-context.ts';
import { scriptedModel } from '../scripted-model.ts';

await runHarnessIpc(async (boot, domain) => {
  const model = await scriptedModel('Synthetic CKD explanation.');
  await model.respond('Synthetic CKD follow-up.');
  await model.respond('Synthetic corrected CKD follow-up.');
  const host = await openLearningHarness({ root: boot.root, profileId: boot.profile_id, storeId: boot.store_id,
    domainStoreId: boot.domain_store_id, domainPath: boot.domain_path, model }, domain);
  let settled;
  return { ...host,
    async status() {
      const requests = await model.requests();
      return { ...await host.status(), modelCalls: requests.length,
        contexts: requests.map(request => ({ messages: describeNativeContext(request.messages),
          system: request.messages.filter(message => message.role === 'system') })) };
    },
    settled() { return settled ??= (async () => { await host.settled(); await model.close(); })(); },
  };
});
