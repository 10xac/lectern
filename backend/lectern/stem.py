"""Minimal English suffix stemmer for retrieval (no external dependency).

Two passes: inflectional (``-s``, ``-ed``, ``-ing``) then derivational (``-er``, ``-tion``,
``-ment``, ``-ness``, ``-ly``), so "customers" and "customer" both reach "custom".
"""

from __future__ import annotations

_MIN = 3


def _inflect(w: str) -> str:
    if len(w) <= _MIN:
        return w
    if w.endswith(("ies", "ied")) and len(w) > _MIN + 3:
        return w[:-3] + "i"
    if w.endswith("sses"):
        return w[:-2]
    if w.endswith("ing") and len(w) > _MIN + 3:
        b = w[:-3]
        if b.endswith(("at", "iz", "bl")):
            return b + "e"
        return b[:-1] if len(b) >= 3 and b[-1] == b[-2] and b[-1] not in "lsz" else b
    if w.endswith("ed") and not w.endswith("eed") and len(w) > _MIN + 2:
        b = w[:-2]
        if b.endswith(("at", "iz", "bl")):
            return b + "e"
        return b[:-1] if len(b) >= 3 and b[-1] == b[-2] and b[-1] not in "lsz" else b
    if w.endswith("es") and not w.endswith("ees") and len(w) > _MIN + 2:
        return w[:-2] if w.endswith(("shes", "ches", "xes", "zes", "ses")) else w[:-1]
    if w.endswith("s") and not w.endswith("ss") and len(w) > _MIN + 1:
        return w[:-1]
    return w


def _derive(w: str) -> str:
    if len(w) <= _MIN:
        return w
    for suf in ("tion", "sion", "ment", "ness", "ence", "ance"):
        if w.endswith(suf) and len(w) > _MIN + len(suf):
            return w[: -len(suf)]
    if w.endswith("ly") and len(w) > _MIN + 2:
        return w[:-2]
    if w.endswith("est") and len(w) > _MIN + 3:
        return w[:-3]
    if w.endswith("er") and len(w) > _MIN + 2:
        return w[:-2]
    if w.endswith("e") and len(w) > _MIN + 1 and w[-2] not in "aeiou":
        return w[:-1]
    return w


def stem(word: str) -> str:
    return _derive(_inflect(word))
