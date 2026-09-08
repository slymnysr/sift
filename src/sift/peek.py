"""Getting back exactly what was there.

Every view `sift` produces names the capture it came from, and every gap in it
says how many lines it covers. `peek` is the other half of that promise: the way
back. Without it, a view would be a claim you have to take on trust; with it, a
view is a starting point and the original is one call away.

It returns bytes turned to text and nothing else -- no re-wrapping, no trimming,
no highlighting. A caller asking to see line 412 is usually asking because
something did not add up, and at that moment anything helpful is in the way.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from sift import lines as text_lines
from sift import store
from sift.distill import render


@dataclass(frozen=True)
class Peek:
    handle: str
    text: str
    first_line: int
    last_line: int
    total_lines: int
    byte_count: int
    # How many lines the caller's pattern matched, when there was one. Not the
    # number shown: context is added around each match and the whole answer is
    # capped, so a reader needs both numbers to know whether they saw them all.
    matched: int = 0

    @property
    def is_whole(self) -> bool:
        return self.first_line == 1 and self.last_line == self.total_lines


def bytes_of(handle: str) -> bytes:
    """The bytes behind a handle: a capture's if there is one, otherwise a file's.

    `sift run` writes a handle into its gap marker and `sift outline` writes a
    path, and both markers end the same way -- *sift peek X for any of them*. So
    the way back takes either. The store is asked first, so that a file sitting
    in the working directory under some capture's name can never answer for that
    capture; only a handle that was never captured falls through to disk.
    """
    try:
        return store.read_raw(handle)
    except FileNotFoundError:
        removed = store.gone(handle)
        if removed is not None:
            when = time.strftime("%Y-%m-%d", time.localtime(removed.removed_at))
            raise FileNotFoundError(
                f"capture {handle!r} was removed by sift gc on {when}"
                f" ({removed.byte_count:,} bytes)"
            ) from None
        found = Path(handle)
        if not found.is_file():
            raise
        return found.read_bytes()


# How many lines a search may return before it stops being a way back into a
# capture and becomes a second copy of it. The caller can raise it; the default
# is here so that a pattern matching everything cannot answer with everything.
FOUND_CAP = 200


def peek(
    handle: str,
    start: int | None = None,
    end: int | None = None,
    grep: str | None = None,
    around: int = 3,
    cap: int = FOUND_CAP,
) -> Peek:
    """Lines `start`..`end` of a capture or a file, 1-based and inclusive.

    Out-of-range asks are clamped rather than refused. Someone reading a view saw
    "3,914 lines not shown" and guessed at a number; answering with the nearest
    real lines is more use than an error about the guess.

    With `grep`, the range becomes the window to search rather than the answer:
    every line matching the pattern comes back, with `around` lines on each side
    of it so the match can be read. Nothing here judges -- the pattern is the
    caller's, the matching is exact, and the lines are still the file's own. This
    is the search a view sends you to when its gap says "3,914 lines not shown"
    and you already know the word you are looking for.
    """
    raw = bytes_of(handle)
    text = raw.decode("utf-8", errors="replace")
    lines = text_lines.of(text)
    total = len(lines)

    if total == 0:
        return Peek(handle, "", 0, 0, 0, len(raw))

    first = 1 if start is None else max(1, min(start, total))
    last = total if end is None else max(first, min(end, total))

    if grep is None:
        return Peek(
            handle=handle,
            text="\n".join(lines[first - 1 : last]),
            first_line=first,
            last_line=last,
            total_lines=total,
            byte_count=len(raw),
        )

    hits = _found(lines, grep, first, last)
    chosen = _with_context(hits, around, cap, first, last)
    if not chosen:
        return Peek(handle, "", first, first, total, len(raw), matched=0)

    return Peek(
        handle=handle,
        text=render(lines, chosen, handle),
        first_line=min(chosen),
        last_line=max(chosen),
        total_lines=total,
        byte_count=len(raw),
        matched=len(hits),
    )


def _found(lines: list[str], grep: str, first: int, last: int) -> list[int]:
    """Every line in the window that the caller's pattern matches.

    A pattern that will not compile is searched for as plain text, the same rule
    `keep` follows and for the same reason: someone who typed `main()` meant
    those characters, and answering a mistyped group with an empty result would
    look exactly like a word that is not there.
    """
    try:
        found = re.compile(grep)
    except re.error:
        return [n for n in range(first, last + 1) if grep in lines[n - 1]]
    return [n for n in range(first, last + 1) if found.search(lines[n - 1])]


def _with_context(hits: list[int], around: int, cap: int, first: int, last: int) -> set[int]:
    """The matches, the lines around them, and no more than `cap` of anything.

    The cap is applied match by match rather than to the finished set, so what
    comes back is the *first* matches complete with their context instead of
    every match with its context cut off. A truncated context is worse than a
    missing match: the reader cannot tell it was truncated.
    """
    chosen: set[int] = set()
    for hit in hits:
        nearby = set(range(max(first, hit - around), min(last, hit + around) + 1))
        if len(chosen | nearby) > cap and chosen:
            break
        chosen |= nearby
    return chosen
