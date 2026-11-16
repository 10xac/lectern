# Agents on demand

Every agent in lectern is an instance of one **AgentSpec**, the document in
`backend/lectern/agents/default.json`:

```json
{
  "id": "slide-agent",
  "persona": "…explain this slide the way its presenter would…",
  "behaviour": {"rules": ["…"], "decision": {"answer_at": 0.5, "qualify_band": 0.15, "ask_when": "ambiguous"}},
  "context": ["slide", "notes", "neighbours", "deck_outline", "dna", "attachments"],
  "model": {"provider": "fake", "model": null, "api_key_env": null, "base_url": null},
  "tools": ["deck_search", "dna_search", "memory_search"],
  "triage": {"provider": "auto"},
  "budget": {"max_researchers": 4, "max_seconds": 60, "max_tool_calls": 12}
}
```

## Layers

A spec is merged from layers, in this order. Objects merge key by key, lists are replaced, and
an unknown key anywhere is refused (422).

| Layer | Set by |
|---|---|
| `default` | the packaged `default.json` |
| `env` | `LECTERN_PROVIDER`, `LECTERN_MODEL`, `LECTERN_BASE_URL` (v0.1's settings) |
| `deck` | `PUT /decks/{d}/agent` (and the deck's persona) |
| `slide` | `data-agent='{…}'` on an HTML slide, `PUT /decks/{d}/slides/{n}/agent`, or a folder deck slide's `agent` metadata |
| `request` | the `agent` field of an ask: persona, a model from `LECTERN_MODEL_ALLOWLIST`, fewer tools and a lower budget only |

`GET /agents/resolve?deck=&slide=` shows the effective spec, which layer set each field, and
whether the model's key is `set` or `unset`. Keys are never stored, returned, traced or logged:
`model.api_key_env` only *names* the environment variable, which is read when the instance is
built. When a request switches provider, the key variable resets, so one provider's key never
reaches another.

## Jobs

An ask is a **job**: `POST /decks/{d}/slides/{n}/ask` (or `/decks/{d}/ask` for the deck) returns
`202` at once, and `?wait=true` waits for it. The job runs as an `asyncio` task in the API process:

```
triage ─▶ research (one researcher per source, in parallel) ─▶ fuse ─▶ decide ─▶ answer graph
```

- **Researchers** (`jobs/research.py`, `jobs/web.py`): K reads the deck, its DNA and the pages of
  its references; M reads past answers; W searches Exa and fetches a page; P asks the model
  closed-book. They run in worker threads, at most `budget.max_researchers` at once, sharing
  `budget.max_tool_calls`. When `budget.max_seconds` runs out, the job answers from what it has
  and says so.
- **Progress** streams over SSE (`GET /jobs/{id}/events`, replayable from `Last-Event-ID`). The web
  app shows one lane per researcher.
- **Each answer lands on the slide it was asked on** (that slide's thread,
  `GET /decks/{d}/slides/{n}/messages`), whatever slide anyone has open. Many jobs on many slides
  run at once.
- `DELETE /jobs/{id}` cancels. On restart, jobs that were running are marked `failed: interrupted`.

See `docs/confidence.md` for triage, fusion and the decision.
