"""Task 3: the compiler, C[e], from the extended-LAMBDA source AST
(lambda1_vp.py, unmodified) into the pure target language (target_ast.py).

Compilation is compositional (CMP-02): each visit method translates its
subexpressions first (by recursive .accept(self) calls) and combines the
results according to the source constructor; it never calls the shared
evaluator (evaluator.py is not imported here) and never tries to execute
the program, so even a divergent source program compiles successfully.
Because every subexpression is visited regardless of whether it is ever
dynamically selected (both branches of an `if`, a lambda's body whether or
not it is ever applied, both operands of `and`/`or`), unsupported forms are
detected throughout the AST, including in unselected branches and
unapplied function bodies (CMP-07).

Translation rules (C[e] denotes the translation of e; `s,z,t,f,x` and
other short names are never reserved -- compiler-introduced binders are
only the fresh thunk parameters `u`/`v` used for delayed branches, chosen
fresh against the free variables of what they wrap, so source programs
remain free to use any identifier):

    C[n]                   = NUM(n)                      (n >= 0)
    C[true]                = TRUE
    C[false]               = FALSE
    C[x]                   = x
    C[lam x. e]             = lam x. C[e]
    C[e1 e2]                = C[e1] C[e2]
    C[not e]                 = NOT C[e]
    C[e1 + e2]               = ADD C[e1] C[e2]
    C[e1 - e2]               = SUB C[e1] C[e2]              (truncated)
    C[e1 * e2]               = MUL C[e1] C[e2]
    C[e1 < e2]                = LT C[e1] C[e2]
    C[e1 <= e2]               = LEQ C[e1] C[e2]
    C[e1 > e2]                = GT C[e1] C[e2]
    C[e1 >= e2]               = GEQ C[e1] C[e2]
    C[e1 == e2]                = EQ C[e1] C[e2]
    C[e1 != e2]                = NEQ C[e1] C[e2]
    C[if c then t else f]       = (C[c] (lam u. C[t]) (lam v. C[f])) I
    C[e1 and e2]                 = (C[e1] (lam u. C[e2]) (lam v. FALSE)) I
    C[e1 or e2]                   = (C[e1] (lam u. TRUE) (lam v. C[e2])) I
    C[let x = e1 in e2]             = (lam x. C[e2]) C[e1]
    C[pair e1 e2]                    = PAIR C[e1] C[e2]
    C[fst e]                          = FST C[e]
    C[snd e]                           = SND C[e]
    C[fix f(x). e]                      = Z (lam f. lam x. C[e])

`I`, `Z`, and every library combinator (NOT, ADD, SUB, ..., PAIR, FST, SND)
are expanded into pure Var/Lam/App terms by church.py; none of these names
survive into compiler output (CMP-03).
"""
from __future__ import annotations

import os
import sys

_ASSIGN05_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "05")
if _ASSIGN05_DIR not in sys.path:
    sys.path.insert(0, _ASSIGN05_DIR)

import lambda1_vp as src
import church as C
from target_ast import Term, Var, Lam, App, free_vars
from names import fresh_name


class CompileError(Exception):
    """Raised for a source form outside the required language: a negative
    literal, or an unsupported operator spelling (CMP-07). The message
    identifies the offending literal or operator."""


def compile_expr(dexp: "src.d0exp") -> Term:
    """Entry point: translate a source AST into a pure target term."""
    return dexp.accept(_CompileVisitor())


def _compile_if(cond: Term, then_branch: Term, else_branch: Term) -> Term:
    """Shared delayed-branch construction used by if/then/else and by the
    short-circuiting translations of `and` and `or`:

        (cond (lam u. then_branch) (lam v. else_branch)) I

    `u` and `v` are fresh thunk parameters, chosen so that introducing
    them cannot capture a free variable of the branch they wrap (CMP-05).
    They are chosen independently because each only scopes over its own
    branch; a coincidence between them is harmless."""
    u = fresh_name("u", free_vars(then_branch))
    v = fresh_name("v", free_vars(else_branch))
    thunk_then = Lam(u, then_branch)
    thunk_else = Lam(v, else_branch)
    selected = App(App(cond, thunk_then), thunk_else)
    return App(selected, C.I())


_COMPARISON_AND_ARITH = {
    "+": C.ADD,
    "-": C.SUB,
    "*": C.MUL,
    "<": C.LT,
    "<=": C.LEQ,
    ">": C.GT,
    ">=": C.GEQ,
    "==": C.EQ,
    "!=": C.NEQ,
}


class _CompileVisitor(src.D0ExpVisitor[Term]):
    def visit_int(self, dexp: "src.D0Eint") -> Term:
        if dexp.arg1 < 0:
            raise CompileError(f"negative literal not supported: {dexp.arg1}")
        return C.NUM(dexp.arg1)

    def visit_btf(self, dexp: "src.D0Ebtf") -> Term:
        return C.TRUE() if dexp.arg1 else C.FALSE()

    def visit_var(self, dexp: "src.D0Evar") -> Term:
        return Var(dexp.arg1)

    def visit_lam(self, dexp: "src.D0Elam") -> Term:
        return Lam(dexp.arg1, dexp.arg2.accept(self))

    def visit_fix(self, dexp: "src.D0Efix") -> Term:
        f, x = dexp.arg1, dexp.arg2
        body = dexp.arg3.accept(self)
        return App(C.Z(), Lam(f, Lam(x, body)))

    def visit_app(self, dexp: "src.D0Eapp") -> Term:
        return App(dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_if0(self, dexp: "src.D0Eif0") -> Term:
        cond = dexp.arg1.accept(self)
        then_branch = dexp.arg2.accept(self)
        else_branch = dexp.arg3.accept(self)
        return _compile_if(cond, then_branch, else_branch)

    def visit_let(self, dexp: "src.D0Elet") -> Term:
        x = dexp.arg1
        init = dexp.arg2.accept(self)
        body = dexp.arg3.accept(self)
        return App(Lam(x, body), init)

    def visit_pair(self, dexp: "src.D0Epair") -> Term:
        first = dexp.arg1.accept(self)
        second = dexp.arg2.accept(self)
        return App(App(C.PAIR(), first), second)

    def visit_pfst(self, dexp: "src.D0Epfst") -> Term:
        return App(C.FST(), dexp.arg1.accept(self))

    def visit_psnd(self, dexp: "src.D0Epsnd") -> Term:
        return App(C.SND(), dexp.arg1.accept(self))

    def visit_op1(self, dexp: "src.D0Eop1") -> Term:
        if dexp.name != "not":
            raise CompileError(f"unsupported unary operator: {dexp.name!r}")
        return App(C.NOT(), dexp.arg1.accept(self))

    def visit_op2(self, dexp: "src.D0Eop2") -> Term:
        name = dexp.name
        if name == "and":
            e1 = dexp.arg1.accept(self)
            e2 = dexp.arg2.accept(self)
            return _compile_if(e1, e2, C.FALSE())
        if name == "or":
            e1 = dexp.arg1.accept(self)
            e2 = dexp.arg2.accept(self)
            return _compile_if(e1, C.TRUE(), e2)
        if name not in _COMPARISON_AND_ARITH:
            raise CompileError(f"unsupported binary operator: {name!r}")
        left = dexp.arg1.accept(self)
        right = dexp.arg2.accept(self)
        combinator = _COMPARISON_AND_ARITH[name]()
        return App(App(combinator, left), right)
