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
from pathlib import Path

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
        found = Path(handle)
        if not found.is_file():
            raise
        return found.read_bytes()


def peek(handle: str, start: int | None = None, end: int | None = None) -> Peek:
    """Lines `start`..`end` of a capture or a file, 1-based and inclusive.

    Out-of-range asks are clamped rather than refused. Someone reading a view saw
    "3,914 lines not shown" and guessed at a number; answering with the nearest
    real lines is more use than an error about the guess.
    """
    raw = bytes_of(handle)
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
