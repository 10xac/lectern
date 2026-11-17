# Knowing where not to look: per-source confidence

lectern decides where to look **before** it looks, and reports how sure it is **per source**.
This follows the owner's note *Knowing Where Not to Look: query- and source-resolved confidence
for agents*.

## Sources

| | Source | Researcher | Typical r | Ghost mass g |
|---|---|---|---|---|
| K | the deck, its DNA and its references (the trusted base) | BM25, DNA weighted by degree | 0.9 | from the best match score s: max(0.05, 1 − s/(s+2)) |
| M | lectern's memory: past confident answers on this deck (not voted down) | BM25 over past questions | 0.15 + 0.35·(1+👍)/(2+👍+👎), at most 0.5 | 0.5 on a hit |
| W | the open web (Exa + `fetch_url`) | search, then answer from snippets | 0.4 + 0.4·agreement | 0.3 on a hit |
| P | the model's own knowledge | closed-book answer | 0.5 | 0.5 |

Past answers (M) are conversation, not a source: they weigh at most 0.5 against the deck's 0.9,
their disagreement does not count towards the conflict κ, they come last in the answer's context,
and the model is told to follow the sources where the chat or a past answer disagrees.

`r` is the chance the source answers correctly if the answer is in its corpus; `g` is the chance
the answer is not in its corpus at all. A source that finds nothing has g = 0.95 and votes for ∅.

## Triage (`jobs/triage.py`)

From the question and cheap probes (deck and memory BM25 hits, recency words, content words)
triage returns the hurdle `engage`, a route (consult or skip, with a reason, for each source), a
coverage class (`covered | rare | ghost`), the hops and the ambiguity.

- **Rules** (offline, the default): a strong deck match is *covered*, and then W and P are skipped
  ("K holds the answer"). A recency word makes the question *rare* and routes it to W. No match
  anywhere is a likely *ghost*. A question with no content words fails the hurdle.
- **System1** (decision D9): the fast model the owner already configured. jev on OpenRouter's
  decisions endpoint when the main provider is OpenRouter (reusing `LECTERN_API_KEY`) or
  `OPENROUTER_API_KEY` is set. Otherwise a *structured System1* on OpenAI, Gemini or Anthropic
  with the same key, whose JSON output mirrors jev's answers. `SYSTEM1_*` variables override the
  inference. System1 may only narrow the rules' route. 429 and 529 are retried once; any other
  failure falls back to the rules, and the trace says which System1 ran and why. System1 is told
  where the question was asked: the deck's title, the slide's number and title, and the outline
  (cut first to keep the request under 2 KB).
- **Questions anchored in the deck** (v0.4.1): a question about the thing it is asked on ("what is
  this talk about?", "the core ideas of the slide") or one the deck clearly matches is *covered*.
  System1 may lower confidence on it but cannot fail the hurdle, ask back or skip K: `engage` is at
  least 0.9, the ambiguity is the lower of the two, and the ghost mass the lower of the two. K
  then reads the slide asked on and the outline, whatever words they share with the question.
- **The web researcher** runs only when `EXA_API_KEY` is set, which adds `web_search` and
  `fetch_url` to the agent's tools; triage still skips W when K covers the question.

Every job's triage features and outcome are exported at `GET /jobs.jsonl`, so a learned triage can
be trained later.

## Fusion (`jobs/fusion.py`)

Candidates are the sources' answers clustered by normalised text, plus ∅ ("none of these"). Two
answers that share at least half their content words (Jaccard ≥ 0.5) are one candidate, so two
extracts of the same fact are not counted as a conflict.
Both rules are computed and shown side by side.

- **Bayesian:** p(y|e) ∝ p0(y) ∏ₛ [(1−gₛ)(rₛ pₛ(y) + (1−rₛ)u(y)) + gₛ u(y)], with u uniform and the
  prior p0(∅) set to triage's ghost probability. The evidence Z is reported.
- **Dempster–Shafer:** mₛ({ŷₛ}) = rₛ, mₛ(Θ) = 1 − rₛ, combined by Dempster's rule. The conflict κ is
  reported, never just absorbed.

Worked example (a unit test): K says *a* (r 0.9, g 0.2) and W says *b* (r 0.6, g 0.3). Then
κ = 0.9 × 0.6 = 0.54, m({a}) = 0.36/0.46 ≈ 0.78, and m({b}) = 0.06/0.46 ≈ 0.13.

## Decision

| Verdict | When |
|---|---|
| ask | triage's ambiguity ≥ 0.5 (and `ask_when` is `ambiguous`) |
| abstain | the best candidate is ∅, or P(best) is below the band. The answer names the sources checked and the ghost |
| qualify | P(best) is within `qualify_band` of `answer_at`, or κ ≥ 0.5 (the sources clash) |
| answer | P(best) above `answer_at` |

The answer carries a confidence chip per source and one for the fused figure. Hovering shows r,
g, Z and κ. 👍/👎 on an answer feed memory's r.
