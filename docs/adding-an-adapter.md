# Adding an adapter

An adapter turns one file format into a `Deck`. Everything after ingest works on `Deck` and
`Slide`, so a new format needs no change outside `ingest/`.

## 1. Write the parser

Create `backend/lectern/ingest/<format>.py` with:

```python
def parse(data: bytes, name: str = "deck.<ext>") -> Deck:
    ...
    return Deck(title=title, source="<format>", slides=[Slide(n=1, title=..., body=..., notes=...)])
```

- Number slides from 1 in presentation order.
- Put visible text in `body`, one line per paragraph, bullet or table row (`a | b | c`).
- Put presenter or speaker notes in `notes`; an empty string when a slide has none.
- Raise `IngestError` with a helpful message for a file you cannot read.
- Do not touch the network or the store: an adapter is a pure function of the bytes.

## 2. Register it

- Add the source name to `SourceKind` in `models.py`.
- Add the parser to `ADAPTERS` in `ingest/__init__.py`.
- Teach `ingest/detect.py` to recognise the format from its name and first bytes.
- Add a label for it in `frontend/src/components/DeckList.tsx` and the `accept` list in `App.tsx`.

## 3. Test it

- Add a small fixture to `backend/tests/fixtures/decks/` (if it is binary, generate it from a
  script so the repo never holds a file it cannot rebuild).
- Add `backend/tests/test_ingest_<format>.py`: titles, bodies, notes (including a slide without
  notes) and an unreadable file.
- Add the fixture to the parametrised tests in `test_ingest_common.py`.
- Run `make check`; mind the size budget.
