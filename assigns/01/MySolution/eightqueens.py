"""
The Eight-Queens Puzzle
Python 3 translation of eightqueens.dats (original ATS source)

Note: the original ATS `search` function is tail-recursive, and ATS's
compiler eliminates tail calls into a loop (constant stack space).
Python does NOT perform tail-call optimization, so a literal
recursive translation overflows Python's recursion limit for N=8.
This translation converts `search` into an equivalent explicit loop
that reproduces the exact same control flow and behavior.
"""

N = 8


def print_dots(i: int) -> None:
    while i > 0:
        print(". ", end="")
        i -= 1


def print_row(i: int) -> None:
    print_dots(i)
    print("Q ", end="")
    print_dots(N - i - 1)
    print()


def print_board(bd: tuple) -> None:
    for i in range(N):
        print_row(bd[i])
    print()


def board_get(bd: tuple, i: int) -> int:
    if 0 <= i < N:
        return bd[i]
    return -1


def board_set(bd: tuple, i: int, j: int) -> tuple:
    if 0 <= i < N:
        lst = list(bd)
        lst[i] = j
        return tuple(lst)
    return bd


def safety_test1(i0: int, j0: int, i1: int, j1: int) -> bool:
    return j0 != j1 and abs(i0 - i1) != abs(j0 - j1)


def safety_test2(i0: int, j0: int, bd: tuple, i: int) -> bool:
    while i >= 0:
        if not safety_test1(i0, j0, i, board_get(bd, i)):
            return False
        i -= 1
    return True


def search(bd: tuple, i: int, j: int, nsol: int) -> int:
    """
    Iterative equivalent of the tail-recursive ATS `search` function.
    Each branch below corresponds exactly to one tail call in the
    original: instead of calling search(...) again, we update
    (bd, i, j, nsol) and loop.
    """
    while True:
        if j < N:
            test = safety_test2(i, j, bd, i - 1)
            if test:
                bd1 = board_set(bd, i, j)
                if i + 1 == N:
                    print(f"Solution #{nsol + 1}:\n")
                    print_board(bd1)
                    # tail call: search(bd, i, j+1, nsol+1)
                    j, nsol = j + 1, nsol + 1
                else:
                    # tail call: search(bd1, i+1, 0, nsol)
                    bd, i, j = bd1, i + 1, 0
            else:
                # tail call: search(bd, i, j+1, nsol)
                j = j + 1
        else:
            if i > 0:
                # tail call: search(bd, i-1, board_get(bd, i-1)+1, nsol)
                j = board_get(bd, i - 1) + 1
                i = i - 1
            else:
                return nsol


def main() -> None:
    bd0 = (0, 0, 0, 0, 0, 0, 0, 0)
    nsol = search(bd0, 0, 0, 0)
    print(f"Total number of solutions = {nsol}")


if __name__ == "__main__":
    main()
