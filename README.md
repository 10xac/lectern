# lectern

**Every slide of a deck gets its own agent.** Upload a presentation (a Claude artifact deck in
HTML, a PowerPoint `.pptx` with presenter notes, or a Google Slides export), open any slide and
ask it a question. The slide's agent answers from the slide, its presenter notes, the slides
around it and any data the author uploaded, and it cites what it used. Click a citation chip to
jump to the slide it came from.

v0.2 adds three things. **Agents on demand:** every agent is an instance of one spec, and one
question can start several research agents in parallel in the background, each answer landing on
the slide that was asked. **Knowing where not to look:** a triage step picks which sources to
consult before any search runs, and each answer shows its confidence per source. **The conceptual
DNA:** people and AI tools (over MCP) record the ideas, reasoning and references that shaped each
slide, and lectern shows them as a graph and as a trace.

lectern is small on purpose (about 5,000 lines of Python and TypeScript) so that you can read all
of it in an afternoon. It runs fully offline: the default "model" is a deterministic extractive
stand-in, so you need no API key to use it, test it or change it.

## Quick start

You need [uv](https://docs.astral.sh/uv/) (it fetches Python 3.12) and Node.js 22.12 or newer
(its bundled `corepack` provides the pinned `pnpm`).

```bash
git clone https://github.com/10xac/lectern.git
cd lectern
make install   # uv sync + pnpm install, both from lockfiles
make dev       # API on http://127.0.0.1:8000, web app on http://localhost:5173
```

The first `make dev` ingests the three sample decks in `decks/` into `lectern.db`.
`make help` lists every target.

## Your first question

1. Open http://localhost:5173 and click **Kettle & Co. quarterly review**.
2. Click slide **2, Revenue by region**, and press **Show notes**.
3. In the chat on the right, ask: *Why did the harbour cafe grow?*
4. The answer comes from `slide-2` with chips such as `slide 2 · notes`. Click a chip to jump.
5. Press **trace** under the answer to see each graph step, the blocks it used and its timing.

Now ask slide 2 *What did customers say on slide 4?*: slide 4's agent answers (a handoff). Ask
*Summarise the deck* and the deck agent answers.

The same from a terminal:

```bash
uv run lectern seed decks
uv run lectern ask 2 2 "Why did the harbour cafe grow?"
```

## Your first DNA

```bash
make demo   # an AI client builds a 6-slide deck over MCP and logs its DNA, then asks three slides
DB=demo.db LECTERN_BLOBS=demo-blobs make dev
```

1. Open **knowing-where-not-to-look**, slide **2**, and press **DNA**. The graph shows what shaped
   the slide: a deck-wide *general* idea at the top, the slide's *high* and *medium* records below
   it, and the sources table they target. Switch to **Text** for the ordered trace.
2. Press **+ New influence**, choose **choose slides**, tick 2 and 3, set the degree to **high**,
   add a link, and save. The record shows on exactly those two slides.
3. Ask slide 5 *What is ghost mass and what reduces it?* Watch the researcher lanes. The answer
   cites the DNA record (chip **DNA**), and the chips show each source's confidence.
4. Ask anything the deck cannot know. The agent abstains and says which sources it checked.

To let Claude Code log the DNA of the deck it is building:
`claude mcp add lectern -- uv run --directory "$PWD" lectern mcp`. See `docs/dna.md`.

The demo runs offline. With keys in `.env` (`LECTERN_PROVIDER`, `LECTERN_API_KEY` and
`LECTERN_MODEL` for a real model, `EXA_API_KEY` for the web, `OPENROUTER_API_KEY` for jev triage)
the same command uses them.

## Present and share

Open a deck and press **Present** for a full-screen talk (←/→, Esc; the audience can press **Ask**
to question the slide on screen). **Share** makes a deck private (signed-in people only), public
(anyone with the `/d/<id>` link can view it, ask its agents and read its DNA) or public behind a
password. Each visitor's chat is their own, and their questions count against the server's rate
limits and daily budget.

## Connect Claude (MCP)

- **claude.ai:** Settings → Connectors → *Add custom connector*, URL `https://<your host>/mcp`.
  Claude sends you to lectern to sign in and approve; nothing to paste.
- **Claude Code:** create a token under *Connect → MCP tokens*, then
  `claude mcp add --transport http lectern https://<your host>/mcp/ --header "Authorization: Bearer <token>"`,
  or run it locally with `claude mcp add lectern -- uv run --directory "$PWD" lectern mcp`.

Claude can then list and read decks, put and edit slides (`put_slide`, `edit_slide`), log the DNA
(`add_influence(s)`), share a deck and ask questions. See `docs/dna.md`.

## How it works

```
upload ─▶ ingest graph: detect → parse → normalise → index → persist ─▶ SQLite
ask    ─▶ answer graph: gate → route → assemble → answer → cite → persist ─▶ {answer, citations, agent, trace_id}
```

| Piece | Where |
|---|---|
| Data model (Deck, Slide, Answer, Citation …) | `backend/lectern/models.py` |
| Storage (stdlib `sqlite3`) | `backend/lectern/store.py` |
| BM25 search, always scoped to one deck | `backend/lectern/search.py` |
| Format adapters | `backend/lectern/ingest/` |
| The graph: state, templates, runner, nodes | `backend/lectern/graph/` |
| Slide agents and the deck agent | `backend/lectern/agents.py` |
| Model providers (`fake`, `anthropic`, `openai_compat`) | `backend/lectern/providers/` |
| HTTP API (FastAPI) and CLI | `backend/lectern/api.py`, `backend/lectern/cli.py` |
| AgentSpec and its layers | `backend/lectern/agents/` (`docs/agents.md`) |
| Jobs: triage, parallel researchers, fusion, decision | `backend/lectern/jobs/` (`docs/confidence.md`) |
| The DNA, the file registry, folder decks | `backend/lectern/dna/`, `files.py`, `blobs.py`, `folders.py` (`docs/dna.md`) |
| One facade for REST, MCP and CLI; the MCP server | `backend/lectern/hub.py`, `backend/lectern/mcp_server.py` |
| Web app (React + Vite + TypeScript, Tailwind, react-router) | `frontend/src/` |

## How to read the graph

Start with `backend/lectern/graph/templates.py`: two short templates say which nodes run, in
which order, and which backward edges are allowed. Then read `graph/runner.py`, which runs a
template one node at a time. Each node in `graph/nodes/` is a small function that takes the
frozen state and returns the fields it changes plus where to go next. `docs/graph.md` walks
through one question step by step.

## Using a real model

The `fake` provider ranks the sentences of the context blocks against your question and
returns the best three with their block ids, so its answers are extracts, not prose. To use a
real model, copy `.env.example` to `.env` and set `LECTERN_PROVIDER` (`anthropic` or
`openai_compat`), `LECTERN_API_KEY` and `LECTERN_MODEL`. Real providers are never used in tests.

## How this is tested

`make check` runs everything CI runs:

| Check | What |
|---|---|
| `ruff`, `mypy --strict` | backend lint, format and types |
| `pytest -q` | backend tests in `backend/tests/`: every adapter on its fixture, the runner (order, loop caps, step cap, persist last), each node, the agents end to end and the API through FastAPI's `TestClient` |
| `pnpm lint typecheck test` | eslint, `tsc`, and vitest + Testing Library tests (`*.test.tsx`) for the viewer, the per-slide chat and the citation chips |
| `scripts/loc_budget.py` | the size budget (below) |
| `scripts/check_forbidden_paths.py` | repository hygiene |

Tests are offline and deterministic: an in-memory SQLite store, the `fake` provider and a fake
clock (so trace timings are exact). Each side runs in a few seconds. The fixture decks live in
`backend/tests/fixtures/decks/`; the `.pptx` files are built by `scripts/make_sample_pptx.py`
and a test checks that the checked-in files match what the script builds.

Jobs, triage and fusion are tested with fake sources and a fake HTTP port (Exa, OpenRouter and
`fetch_url` are never called), the MCP tools with the SDK's in-memory client, and the DNA graph
against a golden file.

**Size budget** (non-blank, non-comment lines): backend ≤ 5,400, frontend ≤ 3,900 (raised from
1,800 for the redesigned web app: router, app shell, component library, present mode, sharing and
admin pages), tests ≤ 3,600; no file over 300 lines and no function over 60.

## More

- `docs/architecture.md`: the parts and how a request flows through them
- `docs/graph.md`: the graph runner and both templates in detail
- `docs/adding-an-adapter.md`: support a new deck format
- `docs/agents.md`, `docs/confidence.md`, `docs/dna.md`: v0.2's agents, confidence and DNA
- `docs/specs/`: the v0.2 spec and the decisions taken while building it
- `deploy/README.md`: run it behind nginx with Docker (one container, login, rate limits, backups)
- `docs/glossary.md`: the words used in the code
- `CONTRIBUTING.md`: how to propose a change

The sample decks in `decks/` are original work written for this repository and are covered by
its licence. MIT licensed: see `LICENSE`.
