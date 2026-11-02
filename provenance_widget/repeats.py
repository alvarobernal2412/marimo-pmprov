"""Flag sequences of steps that were run again: the same steps, with the same arguments, one after another.

A single step run twice is normal (the same filter at two points of an analysis), so it is not flagged. What is flagged is a
run of `min_length` or more consecutive steps that comes back later, as when a whole part of a notebook is executed again.
Nothing is filtered or removed: the history is untouched, and the flags only say where to look.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable, Sequence

DEFAULT_MIN_LENGTH = 4


@dataclass
class RepeatedRun:
    length: int
    first: int  # position (0-based) of the first time the sequence was run
    repeats: list[int] = field(default_factory=list)  # positions where it was run again


def find_repeated_runs(keys: Sequence[Hashable], min_length: int = DEFAULT_MIN_LENGTH) -> list[RepeatedRun]:
    """Repeated sequences in `keys`, one entry per sequence, listing every later repeat of it.

    `keys` has one item per step, in the order they were run; two steps are the same when their items are equal. Repeats
    never overlap each other or the sequence they repeat, and a repeat is counted once, as part of the longest sequence
    that contains it.
    """
    if min_length < 2:
        raise ValueError("a repeated sequence has at least 2 steps")
    n = len(keys)
    if n < 2 * min_length:
        return []

    # common[i][j]: how many steps in a row, from i and from j, are the same
    common = [[0] * (n + 1) for _ in range(n + 1)]
    candidates: list[tuple[int, int, int]] = []  # (length, later start, earlier start)
    for i in range(n - 1, -1, -1):
        for j in range(n - 1, i, -1):
            if keys[i] == keys[j]:
                common[i][j] = common[i + 1][j + 1] + 1
                length = min(common[i][j], j - i)  # the repeat starts after the original ends
                if length >= min_length:
                    candidates.append((length, j, i))

    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
    taken = [False] * n
    clusters: dict[tuple, RepeatedRun] = {}
    for length, later, earlier in candidates:
        if any(taken[later : later + length]):
            continue
        for position in range(later, later + length):
            taken[position] = True
        pattern = tuple(keys[earlier : earlier + length])
        run = clusters.get(pattern)
        if run is None:
            clusters[pattern] = RepeatedRun(length, earlier, [later])
        else:
            run.first = min(run.first, earlier)
            run.repeats.append(later)
    runs = list(clusters.values())
    for run in runs:
        run.repeats.sort()
    runs.sort(key=lambda r: r.first)
    return runs


def _span(start: int, length: int) -> str:
    return f"{start + 1} to {start + length}"


def describe_run(run: RepeatedRun) -> str:
    """One sentence, with 1-based step numbers."""
    if len(run.repeats) == 1:
        return f"Steps {_span(run.repeats[0], run.length)} repeat steps {_span(run.first, run.length)}."
    spans = [_span(r, run.length) for r in run.repeats]
    where = " and ".join(spans) if len(spans) <= 2 else ", ".join(spans[:-1]) + " and " + spans[-1]
    return f"Steps {_span(run.first, run.length)} are repeated at steps {where}."
