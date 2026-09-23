import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lambda0 import *

# --- Given examples from the assignment spec ---

assert t0erm_size(T0Mpair(T0Mint(1), T0Mint(2))) == 3

assert t0erm_fvset(T0Mpfst(T0Mpair(T0Mvar("x"), T0Mvar("y")))) == frozenset({"x", "y"})

assert t0erm_cbv_evaluate0(
    T0Mpsnd(T0Mpair(T0Mint(1), T0Mop2("+", T0Mint(2), T0Mint(3))))
) == T0Mint(5)

print("Given examples: OK")

# --- Sizes and free-variable sets of nested pairs/projections ---

# A pair of pairs: T0Mpair(T0Mpair(1,2), 3)
nested = T0Mpair(T0Mpair(T0Mint(1), T0Mint(2)), T0Mint(3))
assert t0erm_size(nested) == 5  # 1 (outer pair) + 3 (inner pair+2 ints) + 1 (int 3)

# fst of a pair whose components are variables, nested inside another pair
term = T0Mpair(T0Mpfst(T0Mpair(T0Mvar("a"), T0Mvar("b"))), T0Mvar("c"))
assert t0erm_fvset(term) == frozenset({"a", "b", "c"})

# psnd applied to a pair, itself the operand of pfst (nested projections)
nested_proj = T0Mpfst(T0Mpair(T0Mpsnd(T0Mpair(T0Mvar("x"), T0Mvar("y"))), T0Mvar("z")))
assert t0erm_fvset(nested_proj) == frozenset({"x", "y", "z"})

print("Nested size/fvset tests: OK")

# --- Substitution into pairs/projections, including under binders ---

# Simple case: substitute x -> 42 inside a pair
t = T0Mpair(T0Mvar("x"), T0Mvar("y"))
result = t0erm_subst0(t, "x", T0Mint(42))
assert result == T0Mpair(T0Mint(42), T0Mvar("y"))

# Substitute inside a projection operand
t = T0Mpfst(T0Mpair(T0Mvar("x"), T0Mint(1)))
result = t0erm_subst0(t, "x", T0Mint(99))
assert result == T0Mpfst(T0Mpair(T0Mint(99), T0Mint(1)))

# Substitution reaches into a pair nested INSIDE a lambda body,
# where the lambda's bound variable is different from the one being substituted
t = T0Mlam("y", T0Mpair(T0Mvar("x"), T0Mvar("y")))
result = t0erm_subst0(t, "x", T0Mint(7))
assert result == T0Mlam("y", T0Mpair(T0Mint(7), T0Mvar("y")))

# Substitution is BLOCKED when the lambda's bound variable shadows the substituted name
t = T0Mlam("x", T0Mpsnd(T0Mpair(T0Mvar("x"), T0Mvar("z"))))
result = t0erm_subst0(t, "x", T0Mint(7))
assert result == t  # unchanged: "x" is bound by the lambda, so it's shadowed

# Same shadowing check but with T0Mfix (recursive function has two binders: f and x)
t = T0Mfix("f", "x", T0Mpair(T0Mvar("f"), T0Mvar("x")))
result = t0erm_subst0(t, "f", T0Mint(7))
assert result == t  # unchanged: "f" is bound by the fix

print("Substitution under binders tests: OK")

# --- Evaluation: pair construction, both projections, forced evaluation order ---

# Pair whose components require actual computation
t = T0Mpair(T0Mop2("+", T0Mint(2), T0Mint(3)), T0Mop2("*", T0Mint(4), T0Mint(5)))
result = t0erm_cbv_evaluate0(t)
assert result == T0Mpair(T0Mint(5), T0Mint(20))

# Both projections of that same pair
assert t0erm_cbv_evaluate0(T0Mpfst(t)) == T0Mint(5)
assert t0erm_cbv_evaluate0(T0Mpsnd(t)) == T0Mint(20)

# fst still forces evaluation of a failing second component (proves both sides evaluated,
# not just the selected one — see README for discussion of testing evaluation order)
try:
    t0erm_cbv_evaluate0(
        T0Mpfst(T0Mpair(T0Mint(1), T0Mop2("/", T0Mint(1), T0Mint(0))))
    )
    assert False, "should have raised ZeroDivisionError"
except ZeroDivisionError:
    pass

# Mirror case: psnd still forces evaluation of a failing FIRST component
try:
    t0erm_cbv_evaluate0(
        T0Mpsnd(T0Mpair(T0Mop2("/", T0Mint(1), T0Mint(0)), T0Mint(1)))
    )
    assert False, "should have raised ZeroDivisionError"
except ZeroDivisionError:
    pass

print("Evaluation / forced-evaluation tests: OK")

# --- Nested pairs and pairs containing different kinds of values ---

# Pair containing an int and a bool
mixed = T0Mpair(T0Mint(1), T0Mbtf(True))
assert t0erm_cbv_evaluate0(mixed) == T0Mpair(T0Mint(1), T0Mbtf(True))

# Pair containing a string and a nested pair
mixed2 = T0Mpair(T0Mstr("hi"), T0Mpair(T0Mint(1), T0Mint(2)))
result = t0erm_cbv_evaluate0(mixed2)
assert result == T0Mpair(T0Mstr("hi"), T0Mpair(T0Mint(1), T0Mint(2)))
assert t0erm_cbv_evaluate0(T0Mpsnd(mixed2)) == T0Mpair(T0Mint(1), T0Mint(2))

# Deeply nested pair: ((1,2),(3,4))
deep = T0Mpair(
    T0Mpair(T0Mint(1), T0Mint(2)),
    T0Mpair(T0Mint(3), T0Mint(4)),
)
result = t0erm_cbv_evaluate0(deep)
assert result == deep
# fst of fst should be 1, snd of snd should be 4
assert t0erm_cbv_evaluate0(T0Mpfst(T0Mpfst(deep))) == T0Mint(1)
assert t0erm_cbv_evaluate0(T0Mpsnd(T0Mpsnd(deep))) == T0Mint(4)

# Pair containing a function (lambda) as one component
fn_pair = T0Mpair(T0Mlam("x", T0Mop2("+", T0Mvar("x"), T0Mint(1))), T0Mint(10))
result = t0erm_cbv_evaluate0(fn_pair)
assert isinstance(result, T0Mpair)
assert isinstance(result.arg1, T0Mlam)
assert result.arg2 == T0Mint(10)

print("Nested / mixed-value pair tests: OK")

# --- Functions that accept or return pairs (substitution during application) ---

# A function that takes a pair and returns its first component plus 1
swap_fst_plus1 = T0Mlam("p", T0Mop2("+", T0Mpfst(T0Mvar("p")), T0Mint(1)))
call = T0Mapp(swap_fst_plus1, T0Mpair(T0Mint(5), T0Mint(99)))
assert t0erm_cbv_evaluate0(call) == T0Mint(6)

# A function that takes two ints and RETURNS a pair
make_pair = T0Mlam("a", T0Mlam("b", T0Mpair(T0Mvar("b"), T0Mvar("a"))))
call2 = T0Mapp(T0Mapp(make_pair, T0Mint(1)), T0Mint(2))
assert t0erm_cbv_evaluate0(call2) == T0Mpair(T0Mint(2), T0Mint(1))

# A function that swaps the two components of a pair it's given
swap = T0Mlam("p", T0Mpair(T0Mpsnd(T0Mvar("p")), T0Mpfst(T0Mvar("p"))))
call3 = T0Mapp(swap, T0Mpair(T0Mint(1), T0Mint(2)))
assert t0erm_cbv_evaluate0(call3) == T0Mpair(T0Mint(2), T0Mint(1))

print("Functions over pairs tests: OK")

# --- Projection applied to a non-pair value must raise TypeError ---

try:
    t0erm_cbv_evaluate0(T0Mpfst(T0Mint(5)))
    assert False, "should have raised TypeError"
except TypeError:
    pass

try:
    t0erm_cbv_evaluate0(T0Mpsnd(T0Mbtf(True)))
    assert False, "should have raised TypeError"
except TypeError:
    pass

try:
    t0erm_cbv_evaluate0(T0Mpfst(T0Mlam("x", T0Mvar("x"))))
    assert False, "should have raised TypeError"
except TypeError:
    pass

print("Non-pair projection TypeError tests: OK")

print()
print("ALL TESTS PASSED")
