# Known Limitations

Current state of the custom 10-question benchmark (Tesla/NVIDIA/Apple 10-Ks):
**8/10 correct (80%)**, `dataset="custom_demo"` — see `backend/scripts/run_custom_eval.py`.
Not to be confused with the real FinanceBench benchmark (150 questions, `dataset="financebench"`),
which is scored separately and is not yet passing (the random 5-question sample run so far
covered companies outside our 3 seeded documents).

## Remaining failures

### custom-04 — Apple employee count
**Symptom:** Hybrid retrieval returns sections about the 2022/2014 Employee Stock Plans, the
audit opinion, and fiscal-year highlights — never the "Human Capital" section that actually
states headcount, even though that section exists in the tree with real content.

**Root cause:** Hybrid retrieval ranking, not tree structure. The tree itself is correct
(verified directly: `document_nodes` has a single "Human Capital" node with real text, properly
nested under "Item 1. Business" after the dedup fixes below). Dense/BM25 fusion + reranking
just isn't surfacing it near the top for this query's phrasing.

### custom-09 — NVIDIA risk factors
**Symptom:** Retrieval surfaces "Item 1A. Risk Factors" itself — a short stub paragraph — instead
of its 30 real child subsections (e.g. "Failure to estimate customer demand accurately...",
"Competition could adversely impact our market share..."), which contain the actual risk
content and are individually thousands of characters long.

**Root cause:** Same category as custom-04 — hybrid retrieval ranking favors the shallow parent
node (whose title literally contains "Risk Factors") over its content-rich children (whose
titles don't share that exact phrase), even though the children are what actually answers the
question.

### custom-07 — Tesla net income (intermittent)
**Symptom:** Passed in one eval run, failed in another, with no code changes in between.
Reproduced standalone immediately afterward and got the correct section on the first try.

**Root cause:** LLM sampling non-determinism. Groq's `llama-3.1-8b-instant` isn't perfectly
deterministic even at `temperature=0` — this is a known characteristic of many hosted inference
backends (batching/kernel non-determinism), not a bug in this codebase. Not fixable at the
application level; the retry loop (grader-triggered) provides some mitigation but doesn't
guarantee catching every case in a single pass.

## Fix path (not yet implemented)

Both custom-04 and custom-09 point at the same underlying gap in `app/retrieval/hybrid.py`:
**parent-vs-children ranking**. Two directions worth trying:

1. **Retune BM25/dense fusion weights** (`_DENSE_WEIGHT` / `_SPARSE_WEIGHT` in `hybrid.py`) —
   BM25 likely over-weights exact title/keyword matches (e.g. "risk factors" appearing in the
   parent's title) relative to dense semantic similarity, which should favor the children's
   actual content for a specific question.
2. **Parent-expansion**: when a container node with thin/stub `full_text` is retrieved, expand
   the result set to include its children automatically (or embed children's content rolled up
   into the parent's own embedding) rather than relying on the parent and children competing
   independently in the same ranked list.

## Fixed this session (for context — not remaining issues)

- Tree hierarchy flattening (wrong sec-parser 10-Q/10-K handling) — `app/ingest/pdf_parser.py`
- Depth-based size mitigation replaced with real two-stage hierarchical navigation —
  `app/retrieval/vectorless.py`
- Duplicate Part/Item/subsection nodes (same title under different parents, or same content
  duplicated across unrelated parents) — `app/ingest/tree_builder.py`
  (`_merge_duplicate_siblings`, `_merge_duplicate_items_across_parts`, `_dedupe_verbatim_nodes`)
- Re-ingestion crash on unique-constraint violation — `app/ingest/pipeline.py`
- Judge over-penalizing correct numeric answers wrapped in extra context/citations —
  `app/llm/prompts.py` (`JUDGE_PROMPT`)
