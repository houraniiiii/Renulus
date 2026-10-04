# Historical nephrology taxonomy labels

Preserved on **2026-10-04** from the inherited baseline's canonical split
catalogs. The recovery record for that baseline dates to 2026-10-01. These
labels are a dated reference; **Renulus has not adopted them as its curriculum**.

| File | Rows | String fields |
| --- | --- | --- |
| [topics.jsonl](topics.jsonl) | 27 | `topic_id`, `topic` |
| [subtopics.jsonl](subtopics.jsonl) | 199 | `topic_id`, `subtopic_id`, `topic`, `subtopic` |

The files contain IDs and labels only. They contain no questions, answers, case
narratives, patient records or evidence passages. Topic and subtopic IDs are
unique; every subtopic's parent ID and topic name match the topics catalog.

Original paths within the preserved inherited baseline:

- `configs/prompts/p4/v1/p4_labeling_topics.jsonl` → `topics.jsonl`.
- `configs/prompts/p4/v1/p4_labeling_subtopics.jsonl` → `subtopics.jsonl`.

Both files were copied byte-for-byte and matched their source SHA-256 hashes.
The inherited P4 prompt pack consumes this split pair; its labeling engine,
prompts and runtime profiles remain in the separate archive.

The legacy flat `configs/prompts/p4/v1/p4_labeling_taxonomy_catalog.jsonl` also
remains archived. It shares the 199 subtopic IDs and parent IDs, but **89 rows
have different labels** from the split pair. It is not an interchangeable
canonical catalog. These inherited labels have not been evaluated as a current
training curriculum, assessment blueprint or clinical standard.
