# Architecture

lectern has three parts: ingest turns a file into a deck, agents answer questions about slides,
and a web app shows both. One SQLite file holds everything.

```
          ┌──────────── frontend (React) ────────────┐
          │ AppShell (sider) · pages/ · deck/          │
          │   SlideRail │ SlideFrame+Notes │ Ask · Ask the deck · DNA │ drawers
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

React with react-router and Tailwind. `api.ts` is the one typed client (shapes in `types.ts`); every
write sends the session's CSRF token.

- `App.tsx` holds the routes. Page paths never reuse an API path (the server answers `/decks`,
  `/files`, `/me/…`, `/admin/settings` itself), so the deck viewer is `/deck/:id` and a shared link
  is `/d/:id`. The server serves `index.html` for any other path without a file extension.
- `layout/` is the signed-in frame (top bar, collapsible sider, account menu) and the sign-in frame.
- `components/ui/` is the design system: `styles.ts` holds the class recipes (buttons, inputs,
  badges); Button, Card, StatusBadge, DataTable, Drawer/Modal (focus trap, Esc, scroll lock),
  ConfirmButton, Toast, PageHeader, SectionTabs, CreatePanel. Colours are CSS variables in
  `index.css`, named in `tailwind.config.js`.
- `deck/DeckViewer` shows the slide rail (multi-select), the slide with its notes, and a panel with
  Ask (this slide), Ask the deck and DNA. `useDeckView` keeps the current slide in `?slide=`.
- `SlideFrame` renders HTML slides at 960×540 in `<iframe sandbox="allow-scripts">`, scaled to fit.
  Without `allow-same-origin`, slide scripts cannot read the app's page, storage or API.
- `useSlideChat` keeps one conversation per `deckId:slide` key (and one for the deck), so each slide
  has its own chat; an answer is posted to the slide it was asked on.
- `pages/PresentPage` is present mode, with an Ask drawer for the audience.

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
