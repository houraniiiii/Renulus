# Local interface contract

Version 1. Engineering details can change additively as flows are integrated.
Python models in `runtime/renulus/contracts.py` are authoritative. Module JSON
shapes are recorded by the module owner and reflected in its renderer types.

- Local API: `/api/v1`; direct JSON results, structured errors.
- Router seam: `create_router(services) -> APIRouter`. Modules own prefixes.
- Repository seam: `services.registry["content" | "knowledge" | ...]`.
- SQLite: `services.db`, a connection per transaction; one migration ledger.
- Paths: `services.paths`, explicit isolated profile and app-owned directories.
- Runtime: `services.registry["provider"]`; all generation obeys one allowlist.
- Events: `id`, `run_id`, `sequence`, `type`, `payload`; one terminal event.
- HTTP mutation retries use `Idempotency-Key` where relevant.
- Temporary-case data and operation metadata remain in process memory.
- Never return provider credentials, raw exception text or patient payloads in logs.

Feature workers may propose small shared changes; the integration owner commits
them once. Do not build a separate server, store, event bus or agent loop.
