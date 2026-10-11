# H07 native child contract — preparation only

2026-10-11. Worker baseline `96dc85f13874123886aa36baa145d49980c94219`.
No H07 production integration or acceptance is claimed. The user requires real
connected H05 closure before H07 acceptance; H02/H04/H05 are also the ticket
dependencies. Parent owns host/Services, canonical authority and publication.
This lane changes only this note and its dedicated native probe.

## Governing requirements

Read the full [H07 ticket](../planning/opencode-v2/tickets/07-delegate-a-bounded-evidence-review-and-stop-its-children.md),
[S1](../planning/opencode-v2/specs/01-harness-control.md),
[S3](../planning/opencode-v2/specs/03-workflows-migration.md),
[architecture](../planning/ARCHITECTURE.md), [parallel ownership](../planning/PARALLEL_WORK.md),
and [harness contract](../../packages/contracts/harness.md). H07 requires:

- Upstream execution/child coordination with role/model/tool grants intersected
  against current parent authority; delayed approvals are revalidated before effects.
- Durable parent/child operation and cancellation epochs, inspectable bounded
  depth/concurrency/output/attempt allowances, and shared dispatch accounting.
- Parent Stop retains ownership until all descendants and finalizers settle;
  late completion cannot wake revoked work or publish results.
- Restart, child failure, denied overrides and revocation during a permission wait.
- Exact source references in child reports, with no automatic learner-memory
  production from those reports. A domain must explicitly qualify publication.
- H02 active-Test/Study exposure checks at child admission, result consumption and
  detached callbacks, without widening scope or dropping revisions/epochs over IPC.

S1 proposes depth **1**, concurrency **2**, output **4,096 tokens** narrowed by
route caps, twelve shared dispatch permits for a foreground/multistage operation,
and zero automatic retries/substitutions/titles. These are proposed defaults
requiring domain validation, not verified native enforcement. Each tool
continuation is another dispatch against the shared allowance. S3 preserves
canonical receipts and cancellation/publication ordering, forbids automatic
uncertain generation replay, and distinguishes settlement from Stop acceptance.

## Primary-source identity and verification

Source: `C:/Renulus/scratch/ocf/src`, attributed by
[UPSTREAM.md](../../upstream/opencode/UPSTREAM.md) and
[cohort.json](../../upstream/opencode/cohort.json) to OpenCode commit
`4b6fea2875e4f2e3e8a8fee181803e54f7056845`. The extracted directory is **not a
Git checkout**. This lane did not rehash the acquired source archive; its recorded
SHA-256 is `b50f959e4a072e10b81f73b144c3017e83e5c8fafcdefc381d627063c8c67761`.
No registry package or moving upstream source was substituted.

The actual fixture loads the materialized `2.0.26` cohort at
`C:/Renulus/scratch/ocf/cohort`. Independently rehashed its inventory
(`146d6a4f63a1a699c749d4ede05cb8fa944181ea62e4dbf8dbd0f11ac3e6bd74`),
the source root manifest and frozen lock, the five source package manifests,
their root junction targets, and **1,557 inventoried payload files** for
core/sdk/plugin/protocol/client. All matched the recorded cohort. Recorded
SHA-256 values of selected inspected primary source files are in
[primary-source01.json](C:/Renulus/scratch/oc-h02-h08/h07/receipts/primary-source01.json).
This identifies the actual inspected bytes and runtime cohort; it is not an
independent source-archive/build reproducibility claim.

## Supported native APIs and their limits

The embedding entry is `@opencode/sdk/effect`,
`OpenCode.create(options, {overrides})` inside an Effect scope.
[SDK effect interface](C:/Renulus/scratch/ocf/src/packages/sdk/src/effect/opencode.ts:20)
uses direct native `sessions.create/get`; other session methods are the typed
in-process protocol client. The probe typechecks and executes these signatures:

```ts
sdk.sessions.create({
  id?, parentID?, title?, agent?, model?, metadata?, permissions?
}) // native Session.Info; child parentID supplies location
sdk.sessions.get({sessionID}) // native Session.Info
sdk.sessions.list({parentID, limit, cursor?}) // page with data and cursor
sdk.sessions.update({sessionID, title?, metadata?, permissions?}) // void
sdk.sessions.prompt({sessionID, id?, text, metadata?, delivery?, resume?})
  // SessionInbox.User, including actual id and payload
sdk.sessions.synthetic({sessionID, id?, text, description?, metadata?, delivery?, resume?})
  // SessionInbox.Synthetic
sdk.sessions.interrupt({sessionID, resume?}) // {interrupted: boolean}
sdk.sessions.wait({sessionID}) // void, waits idle; never starts work
```

These are signature sketches, not new shared types. A root create uses
`location` rather than `parentID`; native create’s TypeScript input requires
one of those choices. `prompt` and `synthetic` unwrap the protocol response’s
`data` field. [Native create input](C:/Renulus/scratch/ocf/src/packages/core/src/session.ts:86),
[protocol create](C:/Renulus/scratch/ocf/src/packages/protocol/src/groups/session.ts:221),
[prompt/synthetic](C:/Renulus/scratch/ocf/src/packages/protocol/src/groups/session.ts:396),
[wait](C:/Renulus/scratch/ocf/src/packages/protocol/src/groups/session.ts:520),
[interrupt](C:/Renulus/scratch/ocf/src/packages/protocol/src/groups/session.ts:746).

### Child grants are snapshots, not current-parent intersections

[Native create](C:/Renulus/scratch/ocf/src/packages/core/src/session.ts:263)
checks the parent exists and inherits its location. It uses
`input.metadata ?? parent.metadata` and `input.permissions ?? parent.permissions`: an
explicit value replaces the snapshot. Generic create does **not** inherit the
parent model and does not itself establish bounded child role/model/tool authority.
The probe proves native create accepts explicit metadata, permission and model
overrides without dispatch, and later parent metadata/permission updates leave
the previously created child’s snapshots unchanged. No execution authorisation
is inferred from successful construction.

The [built-in subagent tool](C:/Renulus/scratch/ocf/src/packages/core/src/tool/plugin/subagent.ts:105)
does more: counts the actual parent chain, enforces `experimental.subagent_depth`
(default 1), resolves the requested agent, rejects a primary-only agent, awaits
permission for `subagent` with that agent as resource, and checks a continued
session is actually the current session’s child. It chooses model in order
explicit override → agent model → captured parent model, then creates/prompts
through native session APIs and starts the native job. This is the correct
execution owner to reuse; it is not the required Renulus intersection proof.
Its parent/agent snapshots were read before the permission wait.

Native rules use last matching rule, not set intersection.
[Permission evaluation](C:/Renulus/scratch/ocf/src/packages/core/src/permission.ts:88)
merges resolved agent rules with session rules. The original
[permission reply](C:/Renulus/scratch/ocf/src/packages/core/src/permission.ts:265)
fulfills its waiting deferred without rerunning `evaluateInput`; the `always`
branch reevaluates *other* pending requests, not the original one. Consequently
an evaluate hook or `tool.execute.before` alone cannot prove revocation while
that original approval waits. The zero-dispatch probe executes that real native
assertion from a registered public fixture command: public SDK methods observe
the pending ask, change parent rules to deny, and reply `once`. The original
assertion permits the marker effect; a post-assert epoch check blocks it. This
proves the decorator seam, not a production parent grant.

### Supported current-authority seams

`context.session.hook("prompt", callback)` receives `sessionID` and `messageID`
where messageID is the **actual user input ID**, before materialization/admission.
Its prompt/metadata/delivery are mutable cloned fields.
[Hook shape](C:/Renulus/scratch/ocf/src/packages/plugin/src/effect/session.ts:14),
[ordering](C:/Renulus/scratch/ocf/src/packages/core/src/session/prompt.ts:29).
The probe observes a preallocated child input ID and replaces caller-supplied
probe metadata with a value from its fixture-owned registry. These probe keys
are illustrative; they are not a production grant schema.
Replay is a separate boundary: native
[prompt reconciliation](C:/Renulus/scratch/ocf/src/packages/core/src/session/session.ts:150)
returns an existing input before running the prompt hook, and can still wake
execution. A decorator must guard **before original.prompt**, including replay;
the prompt hook alone does not fence replay or wake.
Preparation also awaits attachment/skill materialization after the hook. The
exported [SessionInbox.Service](C:/Renulus/scratch/ocf/src/packages/core/src/session/inbox.ts:145)
has generic `reconcile({id,sessionID,type,delivery})` and
`admit({id,sessionID,item})` methods, and an exported `node` at line 275. It is
a source-supported candidate for a final local check after preparation and
before InboxEnqueued publication. Its generic decoration is **not** validated
by the public fixture: the initial wrapper did not satisfy the pinned
TypeScript declaration contract. Parent must publish and verify the final
admission guard/denial mapping; an early prompt hook cannot be its substitute.

The parent must resolve authority from its admitted parent run and actual native
execution registry, bind parent/child operation, attempt, scope/pins and
cancellation identity, and retain the binding before admission can schedule
work. Native tool `messageID` is an **assistant** ID; neither that nor a tool call
ID may substitute for the actual child input ID. Command/payload remain model
arguments only. Child Library/IPC checks retain the inherited exact revision
pins and parent authority; a native metadata field is a correlation hint, not
authority on its own. This carries forward the user-approved domain IPC contract.

[Hook registration](C:/Renulus/scratch/ocf/src/packages/plugin/src/effect/registration.ts:32)
types session hooks with failure channel `never`; do not invent a typed prompt
admission failure. [Tool hooks](C:/Renulus/scratch/ocf/src/packages/plugin/src/effect/tool.ts:21)
give `execute.before` a typed `Tool.Error` failure, actual tool/agent/session/
assistant/call identity and input. Tool transforms can wrap/update the existing
native tool rather than building another agent scheduler.

The embedding graph also supports preserving an implementation’s dependencies
while decorating its service via
`ServiceNode.replace(ServiceNode.mapLayer(nativeLayer => decoratedLayer))`.
[LayerNode.mapLayer/replace](C:/Renulus/scratch/ocf/src/packages/util/src/effect/layer-node.ts:89).
The dedicated fixture typechecks and exercises a **Session.node decoration of
synthetic** and a **Permission.node post-assert decoration** through public
commands/session/permission SDK methods, preserving the native implementations.
Use **Layer.provide(nativeLayer)** around the decorated layer, so the native
service and finalizers remain owned by the runtime scope. Providing the native
layer only to the effect that constructs and returns a service closes that
acquisition before later method calls; the exploratory probe reproduced an
immediately closed permission service with that incorrect composition.

The tested construction is:

```ts
Permission.node.replace(Permission.node.mapLayer(nativeLayer =>
  Layer.effect(Permission.Service, Effect.gen(function* () {
    const native = yield* Permission.Service;
    return Permission.Service.of({ ...native, assert: input =>
      Effect.suspend(() => {
        const admitted = captureTrustedParent(input);
        return native.assert(input).pipe(Effect.andThen(
          checkCurrentParent(admitted, input)));
      }) });
  })).pipe(Layer.provide(nativeLayer))));
```

`captureTrustedParent`/`checkCurrentParent` are proposed parent-owned functions,
not new APIs. The fixture substitutes its private epoch map and rejects through
the already supported `Permission.BlockedError`. Session method decorators have
narrower declared failure unions: do not silently widen them, misuse NotFound,
or claim a typed prompt policy error. Parent must publish the sanitised denial
mapping at the Tool.Error/host boundary before production admission guards land.
The actual dispatch fence must still validate the chosen current
role/model/tool intersection and debit the parent allowance.

### Exact composable safety sequence proposed for parent composition

This sequence reuses the native subagent/session/job owners. Checkpoints are
ordered; each asynchronous gap needs its own current-authority recheck.

| Boundary | Supported seam and required ordering |
| --- | --- |
| Startup | Install Permission/Session service decorations via `mapLayer` + `Layer.provide`, the tool and prompt hooks, and parent dispatch fence in `OpenCode.create(...,{overrides})`; retain the delayed SessionRestart gate before SDK creation forks recovery. Construct candidates with all dispatch closed. |
| Tool request | `tool.execute.before` resolves actual session/assistant/call identity against admitted parent registry and validates requested role/model/depth and continue-target parent link. Wrap the existing native tool execute effect with tool.transform to acquire its logical invocation lease before the first await and release it in ensuring after its finalizers. The before/after hooks alone do not own the whole invocation. Tool arguments choose only work, never grants. |
| Waiting approval | Run the original `Permission.assert` first. Immediately after its completion, recheck current parent scope/configuration/cancellation and the requested child grant. Deny through supported Permission.BlockedError. An earlier permission.evaluate result is insufficient. |
| Child construction or switch | Decorate native Session.create/switchAgent/switchModel. Under the retained lease, recheck the actual parent and proposed effective role/model/tool intersection **before** calling the native method. Capture/register the actual child ID and durable parent/child operation/epoch linkage before releasing construction ownership. Validate replay digest; native create alone returns an existing ID without comparing changed inputs. |
| Actual input admission | Decorate Session.prompt before its reconcile/wake path. Resolve the child from the trusted admitted registry; fix the actual input ID and stable cancellation identity before native admission. The normal prompt hook checks that exact ID and pins trusted scope/revisions/epochs; never use the assistant tool messageID. Recheck at actual admission after awaited preparation, and before replay/wake. Final SessionInbox guard/denial composition remains a parent prerequisite. |
| Actual dispatch | The parent dispatch fence checks the selected native child agent/model/route against the **current** parent intersection, current epochs and budget, then atomically consumes a shared parent attempt permit before transmission. This also covers continuations, auxiliary calls and recovery. |
| Domain callback and result | Resolve the authenticated DomainGrant from the actual child input binding and inherited parent authority. Recheck before domain work, before returning/consuming exact dependencies and in the final canonical publication transaction. Retain handler/CPU/finalizer ownership across cancellation. Child reports do not become Memory producers by default. |
| Detached notification | Decorate native Session.synthetic before admission/wake. Resolve its actual destination and trusted child/job-generation linkage; reject stale or revoked reports before transcript publication. Normal prompt hooks do not run here. Force parked delivery where explicitly admitted; any later wake still requires dispatch authority. |
| Stop / restart | Seal those admissions, drain already leased constructions, stop the actual bounded family, and await native execution + actual job cancel scopes + domain finalizers. Preserve the store owner on observation timeout. Recovery requires the full quiescent native sweep with current durable admissions, not selective claim erasure or refunded dispatch permits. |

The dispatch/publication parts depend on parent prerequisites; the sequence is
not implemented by this fixture. Approval can change again after the post-assert
check, so construction, input, dispatch and publication checks remain mandatory.

### Parent Stop and actual settlement

No family `parentStop` API was found in the inspected core/sdk/plugin sources.
The [foreground subagent finalizer](C:/Renulus/scratch/ocf/src/packages/core/src/tool/plugin/subagent.ts:235)
interrupts that child and cancels its job. Background observers
[outlive their launching plugin](C:/Renulus/scratch/ocf/src/packages/core/src/session/subagent-job.ts:20).
An interrupt acknowledgement for the parent is not recursive descendant proof.

The supported native ownership primitives are:

```ts
SessionExecution.Service.interrupt(sessionID, {
  resume?: boolean, reason?: "user" | "inactivity", awaitSettlement?: boolean
}) // Effect<boolean>; default acknowledges before cleanup
SessionExecution.Service.awaitIdle(sessionID) // Effect<void>
SessionExecution.Service.active // Effect<ReadonlySet<Session.ID>>
Job.Service.cancel(id) // Effect<Job.Info | undefined>
Job.Service.wait({id, timeout?}) // Effect<{info?, timedOut}>
```

[Execution contract](C:/Renulus/scratch/ocf/src/packages/core/src/session/execution.ts:17)
says `awaitSettlement:true` waits the interrupted execution, while `awaitIdle`
rechecks successors. The public SDK interrupt exposes no awaitSettlement option.
[Coordinator](C:/Renulus/scratch/ocf/src/packages/core/src/session/run-coordinator.ts:147)
clears existing wakes on interrupt, but a new wake during cleanup is a new
admission that may restart after settlement.
[Job.cancel](C:/Renulus/scratch/ocf/src/packages/core/src/job.ts:411) publishes
cancelled status and fulfills `done` **before** it awaits `Scope.close`; its
actual cancel effect continues through scope settlement/consumption. Job terminal
status or `jobs.wait` alone is insufficient.

Proposed parent-owned Stop ordering, to validate after prerequisites:

1. Commit cancellation/revocation and seal fresh child/dispatch/synthetic
   admissions before the first await. Retain logical admission leases.
2. Drain already admitted child constructions, register their actual native
   identities, and capture the bounded owned family and job generations.
3. Issue descendant/parent native interrupts and actual job cancellations so
   every owner receives Stop before waiting on their joins. Then await native
   execution idle and tracked cancel/handler/finalizer settlement.
4. Include retained Python domain/CPU ownership and authenticated callback
   settlement. Domain cancellation suppresses publication but cannot release
   capacity while the handler or its finalizer still runs.
5. Report settled only after this proof. A bounded observation timeout retains
   ownership as blocked/uncertain; no competing store owner or late wake is admitted.

Do not hold canonical transactions, conversation/case/recovery physical locks,
or engine guards across these waits (S1). This ordering is a test target, not
proof that parent Stop is implemented or deadlock-free. Idle interrupt/wait in
the probe only verifies API behavior with parked work and zero dispatch.

### Detached reports and restart claims

[SubagentCompletion.deliver](C:/Renulus/scratch/ocf/src/packages/core/src/session/subagent-completion.ts:28)
admits the report with `sessions.synthetic`, normally without `resume:false`.
Its metadata contains source/childID/agent/state, without Renulus epochs or
authority. [Synthetic admission](C:/Renulus/scratch/ocf/src/packages/core/src/session/session.ts:276)
does not run the prompt hook and wakes execution by default. The probe proves
the hook bypass with `resume:false` and observes the supported Session service
decoration at that same admission. Active detached completion suppression is
still unproved. Exact eligible source references must survive report consumption;
neither report text nor native completion status authorises canonical memory.

[Execution claims](C:/Renulus/scratch/ocf/src/packages/core/src/session/execution.ts:84)
are durable at start. Deliberate Stop releases them on terminal settlement;
shutdown preserves them.
[Restart](C:/Renulus/scratch/ocf/src/packages/core/src/session/execution/restart.ts:35)
is explicitly at least once, assumes the previous owner is dead, and has a
durable default ten-resumption counter. That counter is not the parent’s
dispatch permit budget or permission to replay uncertain inference. The sweep
reconciles pending background children, calls `releaseChildClaims(children)`
early, recovers jobs, forks resumes and can wake parents.
[The store implementation](C:/Renulus/scratch/ocf/src/packages/core/src/session/store.ts:225)
clears suspended **child** claims except those in the supplied recoverable list;
it does not know Renulus’s fresh-child admission lease. This is why the entire
sweep needs quiescence rather than a selective parent-only hold.
[SDK host startup](C:/Renulus/scratch/ocf/src/packages/sdk/src/internal/host.ts:50)
forks the sweep after plugin registration; installing a plugin does not itself
hold recovery closed.

Keep the parent’s delayed SessionRestart replacement and full quiescent sweep
barrier. S1 explicitly requires proving that releasing recovery cannot clear a
fresh child claim. This probe replaces the sweep with an owned interruptible
hold and asserts startup entered it once. It creates a fresh SQLite store,
never releases recovery, and does not prove claim preservation, restart behavior
or resumption policy.

## Executed probe and remaining connected tests

Dedicated files:
[fixture](../../packages/harness/test/fixtures/native-child-contract.ts),
[tests](../../packages/harness/test/child-contract.test.ts). Six public native
tests passed, **zero model requests**, real synthetic SQLite, held recovery,
closed model fetch/snapshot, ambient instruction discovery disabled, and an
isolated synthetic environment. TestLLM has no responses/fallback: unexpected
dispatch records a request and defects. No production host, account, provider,
network inference, Library engine or LearningOwner is exercised.

```powershell
# Working directory: packages/harness in this worker checkout
$env:RENULUS_CHILD_CONTRACT_TEST_ROOT = "C:/Renulus/scratch/oc-h02-h08/h07/native"
& "C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe" --test --test-concurrency=1 test/child-contract.test.ts
& "C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe" node_modules/typescript/bin/tsc --noEmit
```

Receipts: [native-child04.txt](C:/Renulus/scratch/oc-h02-h08/h07/receipts/native-child04.txt),
[typecheck04.txt](C:/Renulus/scratch/oc-h02-h08/h07/receipts/typecheck04.txt).
Early probe corrections concerned protocol result unwrapping, omitting
undefined JSON metadata, and retaining decorated native service lifetime. They
are fixture-development corrections, not H07 product red/green acceptance.

After real H05 closure and published parent prerequisites, the connected suite
must demonstrate: denied child override with zero dispatch; parent allowance
shared by foreground/background children and tool continuations; current-policy
revocation after a waiting approval; source/scope/context/cancellation changes
at all admission, dispatch, result and detached boundaries; parent Stop while
native tool/Python CPU finalizers are deliberately held; late completion during
cleanup; process disconnect; and crash/reopen with pending child claims without
automatic uncertain generation replay. Count actual dispatches and assert
canonical receipts/provenance/memory eligibility through the domain facade.
Do not convert these preparation probes into H07 or H02–H08 acceptance.
