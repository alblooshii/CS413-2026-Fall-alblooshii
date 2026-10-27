"""Task 1: the pure target language.

Term ::= Var(name) | Lam(name, Term) | App(Term, Term)

This is a representation wholly separate from the source AST in
lambda1_vp.py. It has exactly these three forms (TGT-01); compiler output
and library combinators must use only these forms (CMP-03, ENC-01).

Terms are immutable (frozen dataclasses): no operation here ever mutates
an input term (TGT-03, RED-05, CMP-06).
"""
from __future__ import annotations
from dataclasses import dataclass
from abc import ABC

from names import fresh_name


class Term(ABC):
    """Abstract base of the three target forms."""


@dataclass(frozen=True)
class Var(Term):
    name: str

    def __repr__(self) -> str:
        return f"Var({self.name!r})"


@dataclass(frozen=True)
class Lam(Term):
    name: str
    body: Term

    def __repr__(self) -> str:
        return f"Lam({self.name!r}, {self.body!r})"


@dataclass(frozen=True)
class App(Term):
    fn: Term
    arg: Term

    def __repr__(self) -> str:
        return f"App({self.fn!r}, {self.arg!r})"


def free_vars(term: Term) -> frozenset[str]:
    """Free variable names of a target term (TGT-03)."""
    if isinstance(term, Var):
        return frozenset({term.name})
    if isinstance(term, Lam):
        return free_vars(term.body) - {term.name}
    if isinstance(term, App):
        return free_vars(term.fn) | free_vars(term.arg)
    raise TypeError(f"not a Term: {term!r}")


def substitute(term: Term, name: str, replacement: Term) -> Term:
    """Capture-avoiding substitution term[name := replacement] (TGT-03, RED-01).

    Does not mutate `term`. Renames a bound variable with `names.fresh_name`
    only when leaving it as-is would let `replacement`'s free variables be
    captured by that binder.
    """
    if isinstance(term, Var):
        return replacement if term.name == name else term
    if isinstance(term, App):
        return App(
            substitute(term.fn, name, replacement),
            substitute(term.arg, name, replacement),
        )
    if isinstance(term, Lam):
        if term.name == name:
            # The substituted name is shadowed by this binder: nothing
            # under it refers to the outer `name` any more.
            return term
        if term.name not in free_vars(replacement):
            return Lam(term.name, substitute(term.body, name, replacement))
        # Capture hazard: `term.name` occurs free in `replacement`, so
        # substituting under this binder as-is would capture it. Rename
        # the bound variable to a fresh name first.
        avoid = free_vars(term.body) | free_vars(replacement) | {name}
        fresh = fresh_name(term.name, avoid)
        renamed_body = substitute(term.body, term.name, Var(fresh))
        return Lam(fresh, substitute(renamed_body, name, replacement))
    raise TypeError(f"not a Term: {term!r}")


def print_term(term: Term) -> str:
    """Render a term per TGT-02: x | (lam x. body) | (fn arg), recursively."""
    if isinstance(term, Var):
        return term.name
    if isinstance(term, Lam):
        return f"(lam {term.name}. {print_term(term.body)})"
    if isinstance(term, App):
        return f"({print_term(term.fn)} {print_term(term.arg)})"
    raise TypeError(f"not a Term: {term!r}")


def alpha_equivalent(t1: Term, t2: Term) -> bool:
    """Structural equality up to consistent renaming of bound variables.

    Used by tests and by the decoders (which must accept alpha-renamed
    encodings, OBS-01) rather than by the reducer itself.
    """
    return _alpha_eq(t1, t2, {}, {})


def _alpha_eq(t1: Term, t2: Term, env1: dict, env2: dict) -> bool:
    if isinstance(t1, Var) and isinstance(t2, Var):
        b1 = env1.get(t1.name)
        b2 = env2.get(t2.name)
        if b1 is None and b2 is None:
            return t1.name == t2.name  # both free: compare literally
        return b1 == b2
    if isinstance(t1, Lam) and isinstance(t2, Lam):
        depth = len(env1)
        e1 = {**env1, t1.name: depth}
        e2 = {**env2, t2.name: depth}
        return _alpha_eq(t1.body, t2.body, e1, e2)
    if isinstance(t1, App) and isinstance(t2, App):
        return _alpha_eq(t1.fn, t2.fn, env1, env2) and _alpha_eq(
            t1.arg, t2.arg, env1, env2
        )
    return False
