"""Deterministic freshness policy for compiler-introduced binders.

Policy (documented in DESIGN.md): to make a name fresh against a set of
names to avoid, try the base name itself; if it is already in use, try
base_1, base_2, base_3, ... in increasing numeric order and take the first
suffix not in the avoid set. This is deterministic (same base + same avoid
set always yields the same fresh name) and never reserves "plain" names
like s, z, t, f, x for compiler use -- those remain free for source
programs to use, since they are only avoided when they actually collide.
"""
from __future__ import annotations


def fresh_name(base: str, avoid) -> str:
    """Return a name derived from `base` that is not a member of `avoid`.

    `avoid` may be any container supporting `in` (a set, frozenset, dict).
    """
    if base not in avoid:
        return base
    i = 1
    while True:
        candidate = f"{base}_{i}"
        if candidate not in avoid:
            return candidate
        i += 1
