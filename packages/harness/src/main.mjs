import { openLearningHarness } from "./learning-host.ts";
import { createLearningGateway } from "./learning-gateway.ts";
import { runHarnessIpc } from "./ipc.ts";
import { withStatelessExtractions } from "./extraction-host.ts";

// This local placeholder only lets native context resolve. Trusted preparation
// replaces it before media filtering; it has no credential or dispatch authority.
await runHarnessIpc(async (boot, domain) => {
  const gateway = await createLearningGateway(domain);
  try {
    const native = await openLearningHarness({
      root: boot.root, profileId: boot.profile_id, storeId: boot.store_id,
      domainStoreId: boot.domain_store_id, domainPath: boot.domain_path,
      model: { providerId: 'renulus', modelId: 'admission', configuration: {
        model: 'renulus/admission', providers: { renulus: {
          package: '@opencode/ai/providers/openai-compatible',
          settings: { baseURL: 'https://denied.invalid/v1' },
          models: { admission: { limit: { context: 1, output: 1 } } },
        } },
      }, client: gateway.client, preparePrimary: gateway.preparePrimary },
    }, domain);
    const host = withStatelessExtractions(native, gateway.generateExtraction, {
      maxOperations: boot.ipc?.max_result_records ?? 256, maxInputChars: 102400,
    });
    let settlement;
    return { ...host, settled: () => settlement ??= (async () => {
      await host.settled();
      await gateway.close();
    })() };
  } catch (error) {
    await gateway.close();
    throw error;
  }
});
