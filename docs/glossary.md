# Glossary

- **deck**: an ingested presentation: title, source format, outline and slides.
- **slide**: one page of a deck, numbered from 1, with title, body text and presenter notes.
- **presenter notes**: what the presenter planned to say; HTML `<aside class="notes">` or
  `data-notes`, PowerPoint notes pages, Google Slides speaker notes.
- **attachment**: author data uploaded for one deck (`.txt`, `.md`, `.csv`), split into **chunks**.
- **slide agent**: the agent for one slide (`slide-<n>`): the `answer` graph run with that slide's
  context and persona.
- **deck agent**: the agent for the whole deck (`deck`), used for questions that span slides.
- **persona**: the instructions an agent answers in; per slide, per deck, or the default.
- **handoff**: a slide agent passing a question about another slide to that slide's agent (at
  most once per question).
- **context block**: a piece of context with a stable id (`slide:4:notes`, `deck:outline`,
  `att:2:0`).
- **budget**: how many characters of context blocks an answer may use.
- **citation**: a block id an answer used, shown as a chip; it must name a block that was in the
  assembled context.
- **template**: a fixed chain of nodes plus its allowed loops (`ingest`, `answer`).
- **node**: one step of a template; a function from state to a `NodeResult`.
- **runner**: runs a template deterministically, with loop caps and a step cap.
- **outcome**: how a run ended: `done`, `refused:*`, `unsupported`, `loop_cap:*`, `step_cap`,
  `error:*`.
- **trace**: the stored record of a run: one row per step with node, outcome, block ids and ms.
- **provider**: the model behind the `answer` node: `fake` (default, deterministic),
  `anthropic` or `openai_compat`.
- **BM25**: the ranking function used for search and by the `fake` provider.

## v0.2

- **AgentSpec**: the one document that defines an agent: persona, behaviour, context sources,
  model binding, tools, triage and budget (`backend/lectern/agents/default.json`).
- **layer**: one source of AgentSpec fields, applied in order: `default` → `env` → `deck` →
  `slide` → `request`. `GET /agents/resolve?deck=&slide=` shows which layer set each field.
- **instance**: one agent run, created for one job from a resolved spec.
- **model binding**: an instance's `provider`, `model`, `base_url` and `api_key_env` (the *name*
  of the environment variable holding the key; the key itself is never stored or returned).
- **request override**: the `agent` field of an ask. It may set the persona, pick a model from
  `LECTERN_MODEL_ALLOWLIST`, keep fewer tools and lower the budget, and nothing else.
- **job**: one asynchronous question with a status (`queued → triaging → researching → fusing →
  answered | abstained | asked | failed | cancelled`), the slide (or deck) it answers on, and a trace.
- **researcher**: an instance that reads one source for one job; several run in parallel.
- **source**: where evidence comes from: `P` the model's own knowledge, `W` the open web, `K` the
  deck plus its DNA and references, `M` lectern's memory of past answers.
- **triage**: the step before any search: the hurdle, the route and the coverage class (`covered`,
  `rare`, `ghost`). It is jev when an OpenRouter key is set, and rules otherwise.
- **r, g**: a source's reliability (correct if the answer is in its corpus) and ghost mass (the
  answer is not in its corpus at all).
- **influence**: one DNA record: what shaped a slide, some slides or the deck.
- **degree**: how strongly an influence shaped its target: `high`, `medium`, `low` or `general`.
- **file**: a blob with a permanent id; its relative path is a renamable alias.
- **folder deck**: a deck kept as one file per slide under a folder path.
