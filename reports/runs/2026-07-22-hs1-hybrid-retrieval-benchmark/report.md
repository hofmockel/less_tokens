# HS1 — Benchmark hybrid lexical + vector retrieval against vector-only search

**Date:** 2026-07-22
**Backlog item:** HS1 (`BACKLOG.md`, P1, Research)
**Status:** Closed — positive result, recommend shipping (tracked as new item **HS2**)

## Why this exists

`_search_sqlite()` (`.claude/tools/search.py:210-278`) ranks purely by dense-vector
cosine similarity (`BAAI/bge-small-en-v1.5`, 384-dim). HS1 asked whether fusing in a
cheap local lexical leg (SQLite FTS5/BM25) via reciprocal-rank fusion (RRF) measurably
improves retrieval, without adding a second service or cross-encoder.

## Methodology

- **Corpora:** two real, already-indexed repositories — `less_tokens` itself (416 chunks,
  code-heavy: 128 code / 181 doc / 107 changelog) and `ever_better` (6,115 chunks,
  doc-heavy: 5,979 doc / 136 changelog, 0 code — a structurally different corpus,
  deliberately chosen to stress the lexical leg differently).
- **Query set:** versioned, hand-built, 14 queries per repo (`queries_less_tokens.json`,
  `queries_ever_better.json`) — 7 "semantic" (paraphrased questions with no literal term
  overlap with the target chunk) + 7 "exact" (a literal identifier/filename/term).
  - Semantic ground truth: one hand-picked `(source_path, source_key)` chunk per query.
  - Exact ground truth: computed automatically at run time as every chunk whose text
    contains the literal term (case-insensitive) — not hand-curated, so it can't be
    biased toward the method being tested.
- **Ranking is at chunk granularity** (`source_path`, `source_key`), not collapsed to
  one-result-per-file like production `_search_sqlite()` — the question that matters is
  whether the *exact right chunk* surfaces, not just the right file.
- **Methods compared:** vector-only (existing production ranking), lexical-only (SQLite
  FTS5 `bm25()`, OR-of-terms — an AND-of-terms first pass was tried and rejected: it
  requires every token, including stopwords, to co-occur in one chunk, which starves any
  multi-word natural-language query and is not how BM25 retrieval is normally done), and
  RRF fusion (`k=60`, standard constant) of the two.
- **Metrics:** recall@5 (`k=5`, matching `search.py`'s printed default), MRR, mean
  latency, and a token-relevant proxy (`chars_to_find`: cumulative snippet chars, capped
  at `DEFAULT_SNIPPET_CHARS=600` per result as in production printing, an agent would read
  through before hitting the correct chunk within top-5; a miss adds a full-file-read
  fallback cost). Also captured: FTS5 index-build time and on-disk size vs the existing
  vector-blob storage.
- **Script:** `bench.py`, run per repo with that repo's own `.venv-tokens` interpreter
  against its live `index.db` (read-only). Raw results: `results_less_tokens.json`,
  `results_ever_better.json`.

## Results

| Repo | Method | Recall@5 (all) | MRR (all) | Mean chars-to-find | Mean latency |
|---|---|---:|---:|---:|---:|
| less_tokens | vector-only | 1.00 | 0.693 | 1149.7 | 36.8ms |
| less_tokens | lexical-only | 0.79 | 0.706 | 7212.7 | 0.3ms |
| less_tokens | **fused** | **1.00** | **0.725** | **1012.4** | 37.2ms |
| ever_better | vector-only | 0.857 | 0.834 | 3656.9 | 39.9ms |
| ever_better | lexical-only | 0.857 | 0.752 | 2983.3 | 1.5ms |
| ever_better | **fused** | **1.00** | **0.860** | **634.8** | 43.0ms |

Index overhead: FTS5 adds 20KB on less_tokens (3.2% of the 639KB vector-blob storage)
and 800KB on ever_better (8.7% of 9.4MB); build time 4ms and 24ms respectively for the
whole corpus.

## Interpretation — the finding differs from the original hypothesis

HS1 was framed around exact identifiers being vector search's weak spot. That did not
hold: vector-only already gets **recall@5 = 1.0, MRR = 1.0** on exact-term queries in
*both* corpora — `bge-small-en-v1.5` encodes rare identifiers/filenames well enough at
this index scale (hundreds to low-thousands of chunks) that there was no floor to raise.
Lexical-only alone is exactly as good on exact queries (also MRR 1.0) but predictably
collapses on paraphrased semantic queries (0.0 recall before the OR-fix; 0.57–0.71 after).

The real, unexpected win: fusion rescued **semantic** queries vector-only missed.
`eb-s2` ("why the ownership rows that used to say vacant now have owners") and `eb-s7`
("example run log entry for a schema migration decision") both ranked outside top-20 on
vector-only alone; RRF's lexical contribution (partial literal-term overlap — "vacant",
"schema migration") pulled both into the top 5. Net effect on `ever_better`: recall@5
0.857→1.00, MRR 0.834→0.860, and — the metric that actually matters for token cost —
mean chars-to-find dropped **82%** (3656.9→634.8), because a miss's fallback full-file-read
cost dominates the average. On the smaller `less_tokens` corpus, exact recall was already
at ceiling so there was no recall to gain, but fusion still improved MRR (0.693→0.725,
mostly ties on `all`-recall) and reduced mean chars-to-find (1149.7→1012.4) by nudging
already-found answers to slightly better ranks.

**No regression observed anywhere** — every fused number is ≥ its vector-only
counterpart across both query types and both repos. Latency cost is negligible (+1-5ms;
the ~35-75ms embedding call already dominates). Storage cost is small (3-9% of existing
vector-blob size) and index build is sub-30ms even for the 6,115-chunk corpus.

## Decision

**Ship.** Fusion strictly dominated vector-only on every measured metric in this
benchmark, at negligible latency/storage cost, with automatic (not hand-picked) ground
truth for the exact-query half of the set. This clears HS1's acceptance bar ("ship only
if it improves ... without regressing ... beyond a stated tolerance") — tolerance here
is moot since nothing regressed.

Recorded as an **Accepted** decision in `DECISIONS.md`. The actual production
integration (FTS5 schema/trigger wiring, `search.py` fused ranking path, migration for
already-installed downstream repos, tests) is deliberately **not** done in this research
spike — that is real, separate engineering work with its own regression risk across every
repo `less_tokens` is installed into, tracked as new backlog item **HS2**.

## Caveats

- Query sets are hand-built (14/repo) and English-only; they establish direction and
  order of magnitude, not a tight confidence interval. `chars_to_find`'s full-file-read
  miss-fallback is a modeling choice, not a measured agent trace — see
  `CHANGELOG.md`'s note on the deleted `test_bench_tokens.py` perf benchmark for why
  fixture-based token claims need this kind of explicit caveat.
- Both corpora are small-to-medium (hundreds to low-thousands of chunks). The result that
  vector-only already nails exact identifiers may not hold at a much larger corpus scale
  or with a smaller/weaker embedding model; HS2 should keep this benchmark's fixtures as
  a regression check rather than assuming the win is scale-invariant.
