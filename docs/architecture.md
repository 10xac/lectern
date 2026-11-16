# Architecture

lectern has three parts: ingest turns a file into a deck, agents answer questions about slides,
and a web app shows both. One SQLite file holds everything.

```
          ┌──────────── frontend (React) ────────────┐
          │ DeckList · Upload · DeckViewer            │
          │   SlideRail │ SlidePane+NotesToggle │ SlideChat+CitationChip │ TracePanel
          └──────────────────┬───────────────────────┘
                             │ /api (Vite proxy in dev)
          ┌──────────────────▼───────────────────────┐
          │ api.py (FastAPI)          cli.py          │
          │            service.py                     │
          │   run_ingest()   attach()   ask()         │
          │        │                     │            │
          │  INGEST template       ANSWER template    │  graph/ (runner + nodes)
          │        │                     │            │
          │  ingest/ adapters    agents.py, search.py │
          │                      providers/           │
          │             store.py (sqlite3)            │
          └───────────────────────────────────────────┘
```

## Data model (`models.py`)

- **Deck**: title, source (`html`, `pptx`, `gslides`), optional persona, outline, slides.
- **Slide**: number `n` (from 1), title, body, presenter notes, the original HTML for HTML decks
  and an optional persona.
- **Attachment / Chunk**: author data split into searchable pieces, always tied to one deck.
- **Answer**: the text, its citations, which agent answered and the trace id.
- **Trace / TraceStep**: one row per graph step.

## A question, end to end

1. `POST /decks/3/slides/2/ask {"question": "Why did the harbour cafe grow?"}`.
2. `api.ask` loads deck 3 and calls `service.ask`, which builds the starting `GraphState` for
   slide 2's agent (`agents.slide_agent`) and runs the `answer` template.
3. `gate` accepts the question; `route` keeps it on slide 2; `assemble` builds context blocks
   (slide 2, its notes, the deck's best-matching attachment chunks, slides 1 and 3, the outline);
   `answer` calls the provider; `cite` keeps the markers that name assembled blocks; `persist`
   writes the trace.
4. The API returns `{answer, citations, agent: "slide-2", trace_id}` and the chat shows chips.

## Storage (`store.py`)

Tables: `decks`, `slides`, `attachments`, `chunks`, `traces`, `trace_steps`. One connection
behind a lock (FastAPI runs routes on a thread pool). All content reads take a `deck_id`.

## Frontend

- `App.tsx` switches between the deck list and one open deck.
- `DeckViewer` owns the current slide number, the trace drawer and the highlighted attachment.
- `SlidePane` renders HTML slides in `<iframe sandbox="allow-scripts">`. Without
  `allow-same-origin`, slide scripts cannot read the app's page, storage or API.
- `useSlideChat` keeps one conversation per `deckId:slide` key, so each slide has its own chat.
- `CitationChip` turns a block id into a label and jumps to its slide or attachment.

## Limits

20 MB per upload, 200 slides per deck, 1,000 characters per question, 4,000 characters of
context per answer.

## v0.2

```
web app ─┐  REST (api.py, jobs/routes.py, dna/routes.py) ─┐
AI tools ─┼─ MCP (mcp_server.py, stdio or /mcp/) ──────────┼─▶ hub.py ─▶ files.py ─▶ blobs (folder | S3)
scripts ─┘  CLI (cli.py) ──────────────────────────────────┘     │       dna/ (influences, graph, trace)
                                                                  │       folders.py (one file per slide)
                                                                  └─▶ jobs/manager.py: triage → researchers
                                                                       (K M W P, in parallel) → fusion →
                                                                       decision → the answer graph
```

- `agents/`: the AgentSpec and its layers (`docs/agents.md`).
- `jobs/`: asynchronous jobs, SSE events, per-slide threads, triage, researchers, fusion and the
  decision (`docs/confidence.md`).
- `dna/`, `files.py`, `blobs.py`, `folders.py`: the conceptual DNA and the file registry
  (`docs/dna.md`).
- New tables: `jobs`, `job_events`, `slide_messages`, `files`, `influences` and
  `influence_history`. New columns, added in place on an existing database: `decks.agent`,
  `decks.file_id`, `decks.folder`, `slides.agent` and `slides.file_id`.
- Decisions taken while building v0.2 are in `docs/specs/v0.2-decisions.md`.
