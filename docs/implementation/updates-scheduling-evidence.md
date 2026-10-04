# Opt-in Updates scheduling evidence

October 4, 2026 (UTC). Owned scheduling lane on build/update-scheduling, created
from 4f443ce8. The parent continuation at 620c4202 remains separate. Scope is
Updates runtime, renderer, focused tests, and this evidence file.

## Working flow and limits

Updates offers a small Automatic checks disclosure. A fresh profile is off,
has no selected routes, and defaults to a 24-hour interval. The learner selects
supported public routes, explicitly enables checking, and saves. Daily, weekly
and 30-day choices are exposed; the API permits 24–720 whole hours. Selecting
sources alone does not enable automatic checking. Existing per-source,
publication, literature and entry-refresh Check now actions remain available.
Check selected now is an explicit bounded batch even when automation is off.

At most 20 routes can be selected. Each sequential batch attempts at most five
routes, with a 50-second per-route deadline around the existing bounded checker.
Overdue remaining routes are deferred at least 60 seconds, then processed by
due time rather than dropped or repeatedly checking the same first five. Failed
checks get at most two scheduled retries, after five and then 30 minutes. A
third failed attempt waits the configured interval. Success clears the retry
and failure counters. Failed/offline checks do not advance successful-check
timestamps or turn discoveries into reviewed evidence.

Stop checks cancels the current transport and defers the selected routes until
the next interval, retaining completed observations and explicit opt-in.
Shutdown cancels both the background batch and guarded manual checks; unfinished
runs remain interrupted rather than successful. Startup recovers in-flight
durable records and resumes due work only for an enabled profile. There is no
Windows task, hosted service, background process after app closure, or unlimited
catch-up query after an offline period.

## Persistence and integration seams

The additive Updates migration 004-scheduling.sql creates update_schedule,
update_schedule_jobs and update_schedule_runs. Earlier applied migrations are
unchanged. The existing central numbered-migration loader applies it before
constructing Updates; no root migration or storage edit is needed. Per-route
due, attempt, successful-check, retry, failure and error fields survive restart.
The latest 100 batch records retain trigger, start/end, checked/failed counts
and completion/error state.

UpdatesService.scheduling registers start and close with Services.on_startup
and Services.on_shutdown. Its manual guard coordinates the existing local
check/refresh endpoints with automatic batches; a concurrent request gets a
retryable 409 source_checks_busy instead of overlapping or building a queue.
This guard assumes the app-owned single local backend for a profile.

Local API: GET and PUT /updates/schedule inspect/save settings; POST
/updates/schedule/check starts a selected batch; POST /updates/schedule/cancel
stops it. Status includes actual offered routes, persisted selected jobs,
availability, cadence, last_run, next_due_at, running and the declared limits.
Unknown selections and extra fields, including credentials, are rejected.

## Supported source boundaries

The scheduler reuses UpdatesService.check_source, Publications.check and
Literature.check. It introduces no search provider, acquisition engine or model.
Supported catalogue routes are registered K00–K18 KDIGO guideline pages,
G01 public ERA Guidance/ERBP, and G02 UK Kidney Association guideline index.
The source row must still match its registered public URL at dispatch.

Digest selections are already explicitly tracked, enabled public PDFs with a
permission reference, associated with those KDIGO/UK Kidney Association routes
and their supported public upload/document paths. ERA member/manual/question
bodies are excluded, including tracked ERA digest bodies. Other publisher
families and rights-dependent register entries are not automatic candidates.
They do not become eligible merely by appearing in the register.

Literature selections use L03 Europe PMC metadata for installed topic IDs and
labels. Each route queries one topic, at most 25 records, with a rolling window
of at least seven days and at least the configured cadence (up to 30 days).
There is no case text or arbitrary free-text query input. Result limits still
mean incomplete discovery; a successful check is not exhaustive evidence
coverage, latest-final verification or educational review.

The existing SourceFetcher retains anonymous HTTPS, trust_env=False, no inherited
auth/cookies, public-DNS/official-host redirect validation, byte limits and
timeouts. No paid/keyed tools, provider calls, external patient collection or
credentials are used by this lane. New observations remain pending and reuse
the existing exact-publication currency seam; source rights, answer keys,
historical attempts and reviewed publication states are not promoted by checking.

## Evidence

Real SQLite tests use controlled synthetic publishers and the existing producers.
They cover disabled startup, opt-in/route validation, UTC due timestamps across
restart, five-route batches/backlog, mutual exclusion with manual API checks,
offline retry exhaustion/recovery with retained success, cancellation before and
during transport, app lifespan shutdown, tracked PDF changes and installed-topic
metadata discovery. Synthetic publication changes remain pending; no educational
review is fabricated.

Renderer tests cover explicit selection/save, daily default, failures and retries,
manual selected checks while off, Stop, disabling/cadence changes and completed
runs between polls. The original Updates review/pagination tests are retained.
The production Flow renderer is checked with the original bundled pack and a
synthetic publisher in an ignored isolated local profile. These are application
rule and UI checks. This lane makes no live network/provider calls; the parent
independently owns dated free-official-source proof in its integration profile.

Verification on October 4, 2026 (UTC):

- python -m pytest tests/updates -q: **34 passed**, including 12 scheduling tests.
- node node_modules/vitest/vitest.mjs run src/modules/updates: **11 passed**.
- npm run build: typecheck, production renderer and build-electron.mjs passed.
- git diff --check: clean.

The built preview used .local/scheduling-preview-profile, with only Content and
Updates modules and an entirely synthetic publisher. Explicit daily K01 opt-in
survived reload; Check selected now produced one pending synthetic discovery,
zero reviewed and zero dismissed records. The automatic settings remained open
through the completed-run queue refresh. Desktop and a narrow viewport were
inspected; the narrow page width was 345 CSS pixels within a 355-pixel window,
with no horizontal overflow. Bundled Source Sans 3 and the existing Flow tokens
were used. Preview state and dependency junctions are ignored, not product data
or committed source evidence. This is not Windows installer or live network proof.
# Live free-source integration proof

At 2026-10-04 22:54 UTC, the integration owner deliberately enabled a three-topic
Europe PMC metadata selection in the task-owned profile: T10, T19 and T21.
The real automatic batch checked all three successfully between 22:54:05 and
22:54:08 UTC, with zero failures. Persisted attempts, success timestamps and the
next daily due times were returned through the local API. No optional key,
generative provider or case payload was used. The batch is complete, and its
discoveries still require explicit review. This proves the selected live free
route rather than every registered publication source. A newly delivered clean
profile keeps automatic checks disabled by default.
