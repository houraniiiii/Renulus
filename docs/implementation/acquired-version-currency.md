# Acquired article version currency

2026-10-04 UTC · Integration decision for issues #6 and #11.

An acquired JATS receipt establishes acquisition, licence and file identity. A
publication-wide review does not establish that every acquired version is final,
current or content-reviewed. Positive currency and restriction-clearing reviews
therefore require the exact acquired edition and original JATS SHA-256 together.
The original hash is independent of the extracted text hash.

The existing version-1 source-status event is extended additively with optional
paired `identity.edition` and `identity.original_sha256`. Partial, null or
malformed bindings are rejected. Canonical source metadata stores the verified
original hash; earlier acquired imports can bind through their retained
`renulus-acquired-v1` provenance note. No database migration is required.

For acquired JATS, an unbound or differently bound review cannot promote final,
latest-final or content-review flags or clear a restriction. A retraction,
repository removal or access loss still reaches all versions of the identified
publication, including versions mapped to different topics. Publication byte
changes invalidate the earlier review. Corrections remain visible without
silently asserting currentness. Existing non-acquired source reviews retain their
established behaviour.

Validation: `uv run pytest tests/knowledge/test_source_status.py
tests/knowledge/test_source_version.py -q` passed **16 checks** against real
SQLite and LanceDB with explicitly synthetic extraction/embedding adapters.
Coverage includes edition and hash differences, review-before-import replay,
legacy provenance, partial bindings, publication restrictions, exact clearing,
older event retry and restore order. This establishes application rules rather
than a medical currency review. The Updates target/outbox/UI and acquired
importer consume this prerequisite in their separately owned lanes.
