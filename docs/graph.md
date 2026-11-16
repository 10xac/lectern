# The graph

A graph run is a fixed chain of small functions (nodes) over one immutable state. The design
keeps four promises:

1. **Templates are code.** `graph/templates.py` lists each template's nodes and the only
   backward edges it may take, each with a cap.
2. **State is frozen.** A node gets a `GraphState` and returns a `NodeResult`: the fields it
   changes (`delta`) and where to go (`next`). It never mutates anything.
3. **The runner is deterministic.** Same template, same state, same node results: same path.
   Timing comes from a clock the caller injects and is only written to the trace.
4. **`persist` always runs last, once.** Whatever happened before (a stop, an error, a cap), the
   trace is written.

## Templates

```
ingest: detect → parse → normalise → index → persist

answer: gate → route → assemble → answer → cite → persist
        route ↺ route    "handoff", cap 1
        cite  → answer   "revise",  cap 2
```

Step cap = nodes + Σ(loop cap × loop length) + 1, so `answer` can never take more than 12 steps.

## The runner (`graph/runner.py`)

For each node in order, the runner calls it and looks at `next`:

| `next` | Effect |
|---|---|
| `continue` | go to the next node |
| `stop(outcome)` | skip to `persist`; the run's outcome is `outcome` |
| `loop(id)` | jump back along the declared loop `id`, if this node is its source and its counter is below the cap; otherwise the outcome is `loop_cap:<id>` |
| an exception | the outcome is `error:<node>.<ExceptionType>` |

If the step cap is reached, the outcome is `step_cap`. A run that reaches the end has the outcome
`done`. `persist` then runs with every earlier step in `state.steps`; it cannot change the
outcome, and its own failure is only recorded on its step.

## The answer nodes

| Node | Kind | Does |
|---|---|---|
| `gate` | pure | refuses an empty question or one over 1,000 characters |
| `route` | pure (model only as a fallback) | `this_slide`, `other_slide(n)` (a handoff) or `deck` |
| `assemble` | reads the store | context blocks with stable ids, fitted to the budget |
| `answer` | calls the provider | a draft with `[block-id]` markers |
| `cite` | pure | keeps markers that name an assembled block; otherwise revise, then give up |
| `persist` | writes the store | the trace |

**Handoffs.** "What is on slide 5?" asked on slide 2 makes `route` switch the state to slide 5's
agent and loop back to `route`. Slide 5's agent may answer or send the question to the deck
agent, but it may not hand off again: a second handoff is refused and the current agent answers.

**Context blocks** have stable ids: `slide:<n>:title`, `slide:<n>:body`, `slide:<n>:notes`,
`deck:outline`, `att:<attachment>:<chunk>`. A slide agent fills its budget in this order: the
current slide, its notes, this deck's attachments, the neighbouring slides, the outline. The deck
agent reads the outline, the best-matching slides, then attachments.

**Citations.** If no marker in the draft names an assembled block, `cite` sends the run back to
`answer` with a hint listing the ids it may use. After two revisions it answers "I can't support
that from this deck." with no citations (outcome `unsupported`).

## Reading a trace

`GET /traces/{id}` (or the **trace** button in the chat) shows one row per step:

```
0 gate      continue
1 route     continue
2 assemble  continue   slide:2:title slide:2:body slide:2:notes att:1:0 …
3 answer    continue
4 cite      continue   slide:2:body slide:2:notes
5 persist   continue
```
