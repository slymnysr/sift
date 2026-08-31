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

from dataclasses import dataclass

from sift import lines as text_lines
from sift import store


@dataclass(frozen=True)
class Peek:
    handle: str
    text: str
    first_line: int
    last_line: int
    total_lines: int
    byte_count: int

    @property
    def is_whole(self) -> bool:
        return self.first_line == 1 and self.last_line == self.total_lines


def peek(handle: str, start: int | None = None, end: int | None = None) -> Peek:
    """Lines `start`..`end` of a capture, 1-based and inclusive.

    Out-of-range asks are clamped rather than refused. Someone reading a view saw
    "3,914 lines not shown" and guessed at a number; answering with the nearest
    real lines is more use than an error about the guess.
    """
    raw = store.read_raw(handle)
    text = raw.decode("utf-8", errors="replace")
    lines = text_lines.of(text)
    total = len(lines)

    if total == 0:
        return Peek(handle, "", 0, 0, 0, len(raw))

    first = 1 if start is None else max(1, min(start, total))
    last = total if end is None else max(first, min(end, total))
    return Peek(
        handle=handle,
        text="\n".join(lines[first - 1 : last]),
        first_line=first,
        last_line=last,
        total_lines=total,
        byte_count=len(raw),
    )
