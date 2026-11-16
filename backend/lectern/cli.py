"""The ``lectern`` command.

    lectern ingest <file>                 ingest a deck, print its id and slides
    lectern attach <deck> <file>          attach author data to a deck
    lectern ask <deck> <slide> "<q>"      ask a slide's agent
    lectern seed [dir]                    ingest every deck in decks/ (and its *.data.* files)
    lectern serve [--port 8000]           run the API (and MCP over HTTP at /mcp)
    lectern mcp                           the MCP server over stdio, for Claude and other AI tools
    lectern put-slide <path> <file>       create or overwrite a slide file in a folder deck
    lectern add-influence <deck> <json>   add one influence or a list ("-" reads stdin)
    lectern dna <deck> [--slide n] [--graph]   a slide's or the deck's DNA
    lectern reconcile                     find missing and unregistered files

Files go to ``$LECTERN_BLOBS`` (a folder, default ``lectern-blobs``, or ``s3://bucket/prefix``).

The database is ``$LECTERN_DB`` (default ``lectern.db``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from lectern import mcp_server, service
from lectern.blobs import blobs_from_env
from lectern.dna import InfluenceIn
from lectern.files import FileError
from lectern.models import IngestError
from lectern.providers.base import get_provider, provider_for
from lectern.store import Store

DECK_SUFFIXES = (".html", ".pptx", ".json")


def ingest_file(store: Store, path: Path) -> int | None:
    run = service.run_ingest(store, path.name, path.read_bytes())
    deck = run.state.deck
    if run.state.deck_id is None or deck is None:
        print(f"{path.name}: {run.outcome}", file=sys.stderr)
        return None
    print(f"deck {run.state.deck_id}: {deck.title} ({len(deck.slides)} slides, {deck.source})")
    return run.state.deck_id


def seed(store: Store, folder: Path) -> int:
    """Ingest each deck in ``folder``; ``<stem>.data.<ext>`` files become its attachments."""
    count = 0
    for path in sorted(folder.iterdir()):
        if ".data." in path.name or path.suffix not in DECK_SUFFIXES:
            continue
        deck_id = ingest_file(store, path)
        if deck_id is None:
            continue
        count += 1
        for data in sorted(folder.glob(f"{path.stem.split('.')[0]}.data.*")):
            service.attach(store, deck_id, data.name, data.read_bytes())
            print(f"  + {data.name}")
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lectern", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest").add_argument("file", type=Path)
    p_attach = sub.add_parser("attach")
    p_attach.add_argument("deck", type=int)
    p_attach.add_argument("file", type=Path)
    p_ask = sub.add_parser("ask")
    p_ask.add_argument("deck", type=int)
    p_ask.add_argument("slide", type=int)
    p_ask.add_argument("question")
    sub.add_parser("seed").add_argument("dir", type=Path, nargs="?", default=Path("decks"))
    p_serve = sub.add_parser("serve")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--host", default="127.0.0.1")
    add_dna_commands(sub)
    args = parser.parse_args(argv)
    if args.cmd == "serve":
        import uvicorn

        from lectern.api import create_app
        from lectern.guard import redact_logs

        app = create_app()
        redact_logs()
        uvicorn.run(app, host=args.host, port=args.port)
        return 0
    store = Store(os.environ.get("LECTERN_DB", "lectern.db"))
    try:
        if args.cmd in DNA_COMMANDS:
            return dna_command(store, args)
        return run_command(store, args)
    except (IngestError, FileError, ValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def run_command(store: Store, args: argparse.Namespace) -> int:
    if args.cmd == "ingest":
        return 0 if ingest_file(store, args.file) is not None else 1
    if args.cmd == "attach":
        att = service.attach(store, args.deck, args.file.name, args.file.read_bytes())
        print(f"attachment {att.id}: {att.name} ({att.chunks} chunks)")
        return 0
    if args.cmd == "seed":
        print(f"seeded {seed(store, args.dir)} decks")
        return 0
    deck = store.get_deck(args.deck)
    if deck is None or deck.slide(args.slide) is None:
        print(f"no deck {args.deck} slide {args.slide}", file=sys.stderr)
        return 1
    answer = service.ask(store, get_provider(), deck, args.slide, args.question, providers=provider_for)
    print(f"{answer.agent}: {answer.answer}")
    print("cites: " + ", ".join(c.block_id for c in answer.citations))
    return 0


DNA_COMMANDS = ("mcp", "put-slide", "add-influence", "dna", "reconcile", "users")


def add_dna_commands(sub: Any) -> None:
    sub.add_parser("mcp")
    p_put = sub.add_parser("put-slide")
    p_put.add_argument("path")
    p_put.add_argument("file", type=Path)
    p_put.add_argument("--mode", choices=["create", "overwrite", "upsert"], default="upsert")
    p_inf = sub.add_parser("add-influence")
    p_inf.add_argument("deck", type=int)
    p_inf.add_argument("json")
    p_dna = sub.add_parser("dna")
    p_dna.add_argument("deck", type=int)
    p_dna.add_argument("--slide", type=int)
    p_dna.add_argument("--graph", action="store_true")
    sub.add_parser("reconcile")
    p_users = sub.add_parser("users")
    p_users.add_argument("action", choices=["create-admin", "list"])
    p_users.add_argument("email", nargs="?")


def dna_command(store: Store, args: argparse.Namespace) -> int:
    """The DNA and file commands: they go through the same Hub as REST and MCP."""
    from lectern.api import build_hub

    hub = build_hub(store, blobs=blobs_from_env())
    if args.cmd == "mcp":
        hub.jobs.recover()
        asyncio.run(mcp_server.build(hub).run_stdio_async())
        return 0
    if args.cmd == "put-slide":
        out: Any = hub.put_slide(args.path, args.file.read_bytes(), args.mode)
    elif args.cmd == "add-influence":
        raw = json.loads(sys.stdin.read() if args.json == "-" else Path(args.json).read_text())
        items = [InfluenceIn.model_validate(i) for i in (raw if isinstance(raw, list) else [raw])]
        out = [i.model_dump() for i in hub.add_influences(args.deck, items, "cli")]
    elif args.cmd == "dna":
        dna = hub.get_dna(args.deck, args.slide, "graph" if args.graph else "text")
        out = dna if args.graph else dna["text"]
    elif args.cmd == "users":
        return users_command(hub, args)
    else:
        out = hub.reconcile().model_dump()
    print(out if isinstance(out, str) else json.dumps(out, indent=2, default=str))
    return 0


def users_command(hub: Any, args: argparse.Namespace) -> int:
    """Seed the first admin: prints a one-time invite link (safe to re-run while still invited)."""
    if args.action == "list":
        for user in hub.users.all_users():
            print(f"{user.id}  {user.email}  {user.role}  {user.status}")
        return 0
    if not args.email:
        print("usage: lectern users create-admin <email>", file=sys.stderr)
        return 2
    existing = next((u for u in hub.users.all_users() if u.email == args.email.strip().lower()), None)
    if existing is not None and existing.status != "invited":
        print(f"{existing.email} is already {existing.status}; manage it in the web app", file=sys.stderr)
        return 1
    user, token = hub.users.invite(args.email, "admin")
    if user.role != "admin":
        user = hub.users.update(user.id, role="admin")
    base = os.environ.get("LECTERN_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")
    print(f"admin {user.email} invited; open this link once to choose a password (valid 7 days):")
    print(f"{base}/#invite={token}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
