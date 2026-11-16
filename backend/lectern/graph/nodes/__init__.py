"""The node implementations, one table per template."""

from __future__ import annotations

from lectern.graph.nodes.answer import answer
from lectern.graph.nodes.assemble import assemble
from lectern.graph.nodes.cite import cite
from lectern.graph.nodes.gate import gate
from lectern.graph.nodes.ingest import detect, index, normalise, parse
from lectern.graph.nodes.persist import persist
from lectern.graph.nodes.route import route
from lectern.graph.state import NodeFn

INGEST_NODES: dict[str, NodeFn] = {
    "detect": detect,
    "parse": parse,
    "normalise": normalise,
    "index": index,
    "persist": persist,
}
ANSWER_NODES: dict[str, NodeFn] = {
    "gate": gate,
    "route": route,
    "assemble": assemble,
    "answer": answer,
    "cite": cite,
    "persist": persist,
}
