# Deeper Retrieval — What's Done and What's Left

## Done (this branch)

1. **Stemming** — `stem.py`: two-pass English stemmer so morphological variants match
2. **BM25F field weighting** — title 2×, body 1.5×, notes 1× (was flat concatenation)
3. **Hybrid retrieval** — optional embedding search + reciprocal rank fusion (`pip install lectern[embeddings]`)
4. **Query logging** — every answer records BM25 scores, blocks, citations, timing → `GET /query-log`
5. **Eval harness** — 15 seed tuples, 2 xfails documenting known BM25 gaps
6. **Answer caching** — LRU keyed on (deck, slide, question, deck content hash)
7. **SQLite WAL mode** — concurrent reads for daily use
8. **NLI citation verification** — optional semantic check (`pip install lectern[nli]`)

## What's Left

### Immediate (before daily use)

- **Install and test embeddings end-to-end**: run `pip install lectern[embeddings]`, embed a real
  deck, verify that the 2 xfail eval cases flip to pass with hybrid search
- **Wire embeddings into ingest**: call `embed_deck()` from the ingest pipeline's persist node
  when the embedder is available, so new decks get vectors automatically
- **Wire embeddings into the assemble node**: pass the `(embedder, estore)` tuple through to
  `search_slides()` so answer queries use hybrid search
- **Wire the answer cache into `service.ask()`**: check cache before running the graph, store
  after; invalidate on deck edit/delete

### After real usage data (~100+ questions logged)

- **Calibrate triage priors**: read the query log, compute what fraction of questions were
  actually covered by K, rare, or ghost; feed these into `triage.py`'s `coverage_of()` to
  replace the hardcoded `{covered: 0.8, rare: 0.15, ghost: 0.05}` defaults
- **Grow the eval set**: harvest real user questions from the query log into the eval fixture;
  aim for 50+ tuples covering each failure class

### Nice-to-have (deeper, not bigger)

- **Cross-encoder reranking**: after hybrid retrieval returns top-K, re-score with
  `cross-encoder/ms-marco-MiniLM-L-6-v2` for higher precision (optional dep)
- **SQLite FTS5**: replace Python BM25 with SQLite's native full-text search for 10× speed
  on large decks (>50 slides)
- **Latency budget**: add `p95 < 5s` monitoring; alert when embedding or NLI model load
  pushes response time past threshold
- **Feedback loop**: let users thumbs-up/down answers (the `Job.feedback` field exists);
  use feedback to weight the memory researcher's reliability in fusion
