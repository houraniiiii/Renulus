# Synthetic recovery capacity checkpoint

2026-10-04 UTC · Issue #12 · isolated `build/recovery-capacity` worktree based on
`1a29f8d3`. This measurement is an experiment, not a supported recovery format.

`scripts/measure_recovery_capacity.py` claims a fresh absolute task-owned directory
and constructs synthetic Library rows against the actual application schema and
published 1.1.0 teaching content. Separate child processes measure the unchanged
legacy exporter and bounded JSONL segment staging into a new SQLite database. It
does not read a live profile, acquired files, credentials, helpers or indexes and
does not rebuild engines or promote profile state. Existing paths, links and
junctions are refused. No source app worker or provider is started.

The measured run used 156 documents and 6,000 passages with 1,536 UTF-8 text bytes
per passage. Context contains a second copy of passage text; metadata, headings,
physical page/item locators, a source-status journal event and current content are
included. SQL omits rebuildable extraction and path columns before scalar reads.

| Measurement | Legacy canonical export | Segmented experiment |
| --- | ---: | ---: |
| Outcome | Refused: `backup_limit` | Validated |
| Serialized canonical bytes | Exceeded 16 MiB | 21,159,825 |
| Segments | — | 6 |
| Python allocation peak | 33,518,648 B | 272,475 B |
| Initial Windows private bytes | 73,940,992 | 74,371,072 |
| Sampled peak Windows private bytes | 114,950,144 | 75,698,176 |
| Elapsed with instrumentation | 1.1268 s | 8.8441 s |

Source/staged row SHA-256 agreed:
`adbcc6708f4f74f3a7b6e43581468900de307c92d8289423155db7c03f90d9ef`.
Workspace peak was 74,337,364 B; final size was 74,217,004 B.

Reproduce with the selected local Python environment and an unused directory:

```powershell
$env:PYTHONPATH = "runtime"
python -B scripts/measure_recovery_capacity.py --source-root C:/path/to/Renulus `
  --work-dir C:/short/fresh-capacity-work --documents 156 --passages 6000 `
  --text-bytes 1536
```

Machine-only synthetic artifacts were written to
`C:/Users/karol/.r-cap-20261004-manual/report.json`; they are not committed.
Five focused tests cover Unicode/citation/journal/content retention, late segment
hash corruption with complete scratch rollback, traversal refusal with an owner
sentinel, finite record budget refusal, and refusal of an existing workspace.

Default experiment bounds are 256 KiB per framed row, 4 MiB per segment, 64 MiB
aggregate canonical data, 200,000 rows, 512 segments, a 1 MiB manifest and a 1 GiB
workspace. The disk observation is not a quota. Sampling every 20 ms can miss
short native allocation spikes, and tracing affects timings. These results do not
establish original-file, engine, power-loss, full-corpus or production recovery
capacity. A 13,000-document measurement has not been run.

Legacy product bounds remain 16 MiB JSON, 100,000 rows, 288 MiB ZIP, 256 MiB
expanded originals, 64 MiB per original, 1,000 originals and a 1 MiB manifest.
The parent reported a growing imported Library of 157 documents, about 10.6 MB
canonical data after extraction omission and about 243 MB originals at this
checkpoint. Acquisition discovery receipts remain excluded. The authorized next
slice is a working additive format-2 segmented ZIP producer, validator and disk
restore; these experiment bounds are not its product policy.
