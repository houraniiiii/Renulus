# Backend finalisation implementation — October 27

The owner's October 27 instruction authorises implementation of
`docs/planning/BACKEND_FINALISATION_SPEC.md` through BF00–BF08, preserving the
existing interface, records, selected engines, subscriptions and models. This
supersedes the earlier specification-only restriction for this task. It does
not turn synthetic checks into account or packaged Windows acceptance.

Starting branch: `codex/design-c-integration`, commit
`1a40d9fc0813eac1672e21427a5a0430933d3aa4`. The T3 workspace aliases
`C:/Renulus/dev/repo`. Existing modified planning/research documents were retained.
No owner profile or credentials are used for development verification.

## Implemented and verified so far

- `packages/backend` introduces the pinned Node 26.4.0/Effect application scope.
  Its explicit compatibility mode owns a hidden Python child and preserves the
  authenticated `/api/v1` transport, response bytes and stream backpressure.
  Python retains canonical/dispatch authority on this route.
- The isolated TS target opens one `node:sqlite` canonical writer thread against
  a complete Python-prepared schema-2 synthetic profile. It validates the exact
  marker, selector, owner, schema inventory and migration checksums. Commands are
  closed and typed; caller control remains responsive during SQLite contention.
- Actual Python/Node schema, export, receipt replay and backup parity have eight
  passing storage tests. Tests also cover late rollback, stale revisions/owners,
  active Test restrictions, overload and draining close.
- The TS sole-owner HTTP flow renames a saved learning conversation, replays its
  receipt without a second mutation, exports compatible records and acknowledges
  shutdown after canonical settlement. One connected test passes.
- Two facade tests pass, including an account-free real Python start/read/close
  and controlled stream/authentication/overload behavior.
- The inherited-pipe worker channel validates the generated Pydantic JSON Schema
  through Effect. Two tests pass for strict decoding and real Node/Python
  chunked artifact transfer/revocation. Worker launch verifies the Windows venv
  launcher/interpreter relationship rather than assuming equal PIDs.
- The bounded worker implementation passed 33 Python tests, including actual
  offline text/PDF/image OCR, HybridChunker and 384-dimensional FastEmbed.
- Independent Sol review reproduced three compatibility-owner defects: consumed
  Effect finalizers after refused shutdown, unexpected death counted as settled,
  and an HTTP readiness probe that could send a token to a foreign listener.
  Explicit retryable closure and a private `renulus-domain/1` launch/control
  channel repair these. Python binds an exclusive socket itself; successful
  closure requires a matching ACK, exit zero and inherited-pipe closure. The
  repair lane passed 17 Node and 15 Python tests. Independent re-review is active.
- BF01 dispatch passed 12 tests, including real canonical-worker transactions,
  reopen, both native subscription serializers, queued revocation and retained
  uncertainty. Positive role defaults and 5/10/20 budgets are implemented; live
  route/counter qualification is separate.
- BF01 plugin lifecycle passed 17 backend and five native tests. It supports
  immutable add/edit/disable/remove, inspected/effective/failed/held selection,
  restart-based omission and actual protected-host registry observation. The
  authenticated TS target API completed the native lifecycle journey. The full
  transformed registry is inspected independently of execution permissions;
  final removal retains the stock tool boundary. Independent review is active.
- The protected Python HTTP broker passed 74 synthetic tests, including actual
  loopback transport and DPAPI in a synthetic namespace. Integration into the
  worker union and final dispatch path is still required.

## Development provider availability

The requested Kimi K3.1 max delegated implementation stopped with HTTP **402**:
`Insufficient available credits for this inference request`. Its partial plugin
work was preserved and completed by GPT 6.1 Sol. No credits were purchased and
Renulus's selected application subscriptions/models were not changed. Sol
continues implementation and separate independent reviews.

Verification uses `C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe`
and `C:/Renulus/dev/python/Scripts/python.exe`. The Node executable matches the
existing pinned SHA-256. No package/provider acquisition is performed by startup.

## Boundaries still open

This is an implementation record in progress, **not a BF00–BF08 completion
declaration**. The TS target currently requires an explicit synthetic marker and
already migrated schema 2; it cannot select the owner's production profile.
Native plugin/dispatch composition, remaining domain tools and producers,
complete worker engine/broker extraction, paired recovery, authority transfer,
live selected-account qualification and matching Windows delivery remain to be
verified in dependency order. Required unavailable capabilities remain open.

The ordinary source-app launcher and existing owner profile remain selected at
their previous acceptance scope while these target flows are integrated.
