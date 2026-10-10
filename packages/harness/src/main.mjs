import { openHarness } from "./host.ts";
import { runHarnessIpc } from "./ipc.ts";

// No provider adapter is installed by the default entry. Activation stays blocked.
await runHarnessIpc(boot => openHarness({
  root: boot.root, profileId: boot.profile_id, storeId: boot.store_id,
  domainStoreId: boot.domain_store_id, domainPath: boot.domain_path,
}));
