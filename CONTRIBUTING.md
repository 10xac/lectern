# Contributing to lectern

Thank you for helping. lectern is a teaching-sized codebase, so the bar is "a newcomer can still
read all of it".

## Workflow

1. Fork and branch from `main`.
2. `make install`, then make your change with a test next to it.
3. `make check` must pass. It runs the same steps as CI.
4. Use [conventional commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`,
   `test:`, `refactor:`, `chore:`, `ci:`.
5. Open a pull request that says what changed and why.

## Rules of thumb

- **Stay in budget.** `scripts/loc_budget.py` fails a change that pushes the backend past 4,600
  lines, the frontend past 1,800, any file past 300 or any function past 60. Prefer deleting code
  to adding it.
- **Keep it deterministic.** No wall clock, randomness or network in the graph or in tests. The
  clock is injected; the `fake` provider is the only one tests use.
- **Every query is scoped by deck.** Anything that reads slides, attachments or chunks takes a
  `deck_id`.
- **Nodes are small and declare their effects.** A node returns the state fields it changes and
  where to go next; it does I/O only through `Ports`.
- **Dependencies** must be permissively licensed (MIT, BSD, Apache-2.0). Python: `uv add`;
  frontend: `cd frontend && corepack pnpm add`.
- **No secrets** in code or fixtures. Configuration comes from environment variables
  (`.env.example`).
