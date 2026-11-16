# The conceptual DNA of a deck

A slide is shaped by ideas, reasoning, notes, citations and references. lectern records each one
as an **influence** and shows them as a graph and as a trace. People record them in the web app,
AI tools over MCP, and scripts over REST or the CLI. All of these call one facade (`hub.py`), so a
record has the same shape whoever wrote it.

## An influence

```text
scope    {kind: slide | slides | deck, slides: [n…]}
target   {component: whole | text | image | chart | layout | concept | element, element_id?, label?}
kind     idea | reasoning | explanation | note | citation | reference
degree   high | medium | low | general          (search weight 1.0 · 0.6 · 0.3 · 0.2)
title, body (markdown, ≤ 10k), refs [{type: url | file, url?, file_id?, label?, quote?}]
author   {type: human | ai, name, tool?, model?}   via: ui | api | mcp | cli    parent_id?
```

Influences store **lasting slide ids**, not numbers. A slide's id is its own file id in a folder
deck, or `<deck file id>#<n>` otherwise. Reordering a deck keeps each record on its slide. Every
edit keeps the previous version (`…/influences/{id}/history`). Each record also remembers the
version of every file it was written for. When a file changes later, the graph marks the record
stale, and the trace says "⚠ written for v1 of …, now v2".

## Files: a permanent id, a renamable path

Slides, decks and references are **files**. Their bytes live in a blob store: a local folder by
default, or S3 / MinIO / R2 with `LECTERN_BLOBS=s3://bucket/prefix` and `uv sync --extra s3`.
Everything else is a SQLite row: id, path, sha256, size, type, version, status and metadata.

| Action | Effect |
|---|---|
| create / overwrite | overwriting keeps the id and metadata; the version rises when the bytes change |
| move | only the path changes |
| delete | the bytes go; the row stays `missing` so its metadata can be relinked (`?purge=true` forgets it) |
| reconcile | finds rows whose bytes vanished and bytes no row knows; same-hash files are suggested as renames |
| relink | attaches a missing row (and its DNA) to the bytes at another path |

In the web app, **DNA → Check files** lists missing files with *Relink to file…* and *Delete
metadata*.

A **folder deck** is one file per slide (`decks/q3/03-revenue.html`; HTML or Markdown). The folder
becomes a deck the first time a slide is put in it. Slides are ordered by `meta.order`, then by
path. An uploaded `.pptx` or single-file HTML deck is kept whole at `uploads/<deck>/<name>`.

## Surfaces

- **Web app:** *+ New influence* opens a drawer with a scope picker (this slide, chosen slides,
  whole deck), a target picker (*Pick on slide* lets you click an element), kind, degree, and
  references (link, upload, or an existing file). *DNA* opens the slide's or the deck's DNA as a
  layered SVG graph or as the text trace.
- **REST:** `/decks/{d}/influences`, `/decks/{d}/files`, `/decks/{d}[/slides/{n}]/dna?format=graph|text`,
  `/slides?path=`, `/file…`, `/files…` (see the docstring in `dna/routes.py`).
- **MCP:** `lectern mcp` (stdio) or `/mcp/` on the API. With login on, `/mcp` needs a personal
  access token (**Account → MCP tokens**), and records are attributed to its owner. 24 tools: `list_decks`, `get_deck`, `get_slide`, `create_deck`, `put_slide`, `read_slide`,
  `update_slide_meta`, `put_file`, `read_file`, `list_files`, `move_file`, `delete_file`,
  `reconcile_files`, `relink_file`, `upload_file`, `add_influence`, `add_influences`,
  `update_influence`, `remove_influence`, `list_influences`, `add_reference`, `get_dna`, `ask` and
  `get_job`.
- **CLI:** `lectern put-slide`, `add-influence`, `dna`, `reconcile`.

Add lectern to Claude Code with `claude mcp add lectern -- uv run --directory /path/to/lectern lectern mcp`.

The agents read the DNA as part of K, weighted by degree, and cite it (`dna:<id>`,
`file:<id>:p<page>`). A citation chip opens the record.
