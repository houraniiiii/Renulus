# Fresh-profile correction bootstrap — October 7, 2026

**The fresh-profile defect is fixed at `0d4b171e97032208dcee71b4ef9b362522daca12`. Matching manufacture is running;
installed acceptance of this fix is still pending.** The launcher remains on
1dde6d90, which passed existing-profile handoff/lifecycle, but fails empty-profile
content activation. Do not describe that artifact as new-user accepted.

## Failure and repair

The first correction-effect run on installed1dde stopped at the first public
source read: K01-2024 returned404. Its new synthetic database contained no active
content pack. The1.3.0 rationale-only successor requires the immutable prior
question; existing1.2 profiles already contained it, masking the fresh-start gap.
The failed receipt retains zero setup rows/checks/imports/attempts. It stays failed.

Bundled bootstrap now installs required published predecessor packs and the
selected corrected release in one transaction. For this release it installs1.2
then1.3, preserving the old immutable key. Failure rolls back the entire operation.
Existing ancestry avoids rescanning older packs; ordinary explicit imports keep
their strict predecessor rule. Source/profile/rights/selected-model behavior is
otherwise unchanged. No dependency/schema/content-byte change.

## Completed validation

- Guarded source0d4:11/11 focused tests passed,8.47s pytest; complete,
  source_unchanged and accepted_stage_pass true, all source checks true,
  no guard violations. Covers fresh activation/reopen, missing/corrupt ancestry,
  atomic rollback, draft exclusion, existing ancestry and ordinary-import policy,
  plus the existing actual upgrade/history guards. No broad sweep.
- Actual hidden source app: fresh profile loads1.3, exposes the reviewed Test
  start control and230 available questions; normal reopen preserves exactly
  two installed packs and zero attempts/imports/provider completions.
  Parent inspected the Test screenshot. Closes0.204/0.186s, no remaining owned
  process, visible/focused test window or renderer error. This is source proof.
- Separate installed compatibility check passed cb59→1dde→normal close using
  the existing synthetic profile: active1.3, canonical records, manual plan and
  actual Mem0 recall preserved; no model call. Both ready derived Memory
  generations are recorded, not claimed byte-identical. Library was empty;
  populated Library-index rollback and arbitrary version/schema downgrade are
  outside this result. Closes0.188/0.206s without remaining owners.

| Receipt | SHA256 |
| --- | --- |
| `C:\rn-finalise-20261005\fresh-content-20261007-01\result.json` | `e0adfd17e92065d133182b2ae85a08f7ef0877cce66b09768e1d85b1304e04e6` |
| `C:\rn-finish-20261007\evidence\connected\fresh-content-source-01\result.json` | `b3183c7083fcbbac1145553ccb7d4e228055ac166456a4ca1e20c703e4cd7b4d` |
| `C:\rn-finish-20261007\evidence\connected\rollback-installed-1dde-01\result.json` | `a6205f5bfd6db5701952dd488f4751895a7f441594b7e5922b7f4469253fb395` |
| Failed `C:\rn-finish-20261007\evidence\update-effects-preparation\runs\installed1dde01\result.json` | `95fa2721e4eacb3356c8f6b45023e60bb10dfd05fc0b5af2d84bc76883441fa7` |

JUnit SHA256 is `e83343c7290819cee840db0ea63db109b9864f67478b2050ef066439871c5a0d`.
External release evidence lives in `C:\rn-finish-20261007\evidence\release-0d4b171e`. Native serial session4089 owns the
matching source0d4 manufacture. Recover its build.log, package-result.json and
build.terminal.json before continuing. No second manufacture is authorized by
this checkpoint. All earlier lanes are integrated and their worktrees retired.

## Next installed slice

`C:\rn-finish-20261007\evidence\update-effects-0d4b171e` preserves the original correction driver as acceptance.pre-fresh-assertions.mjs
and records exactly two reviewed source-pin updates for the fix. The executable
driver adds read-only fresh1.3/ancestry checks before setup and unchanged
selection/zero provider completions after reopen; all effect assertions remain. Bind its fresh slot only
after complete matching manufacture. The original failed profile is preserved;
its later successful source boot is separately attributed. The new installed
profile must establish actual fresh activation and correction effects: two new
synthetic notes, one saved reviewed attempt, real Updates review, targeted
eligibility exclusion, unaffected control, immutable historical score/key and
normal reopen/idempotency. No publisher or provider request; not clinical proof.

Retain accepted cb59 core, b8 dated-body and1dde handoff evidence with precise
unchanged-source qualification. Promote0d4 only after its own installed check.
The full64-requirement goal remains open for the recorded content/currency and
broader physical accessibility/performance scopes; no new quotas or lost credit.
