"""Choosing which lines to show, without ever writing one.

This is the idea the whole tool rests on. The capture is numbered and handed to
a model with a single question -- *which numbers matter?* -- and the model
answers with numbers. Whatever else it says is thrown away without being read.
The view is then printed from the file on disk, line by line, byte for byte.

That is why `sift` is not a summariser and cannot be compared to one. A
summariser writes a sentence about your output and can be wrong about what your
output said. Nothing here writes a line. Being wrong is still possible -- the
wrong lines can be chosen -- but the cost of that mistake is a line missing from
a view, never a line that says something the command never said. And a missing
line is one `sift peek` away, because the file was never touched.

It is also why coverage is not a list. Nothing in this file knows what a stack
trace looks like in Rust, or what a Japanese error message says, or how a
language released last week reports a failure. The model knows all of that
already. There is no table here to be missing an entry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sift import lines as text_lines
from sift.capture import Capture
from sift.model import Bridge

# Every question asked through `select` is answered the same way, because one
# parser reads every answer. It is kept apart from the questions so that adding a
# second question cannot quietly add a second format for the reply.
ANSWER_FORMAT = (
    "\n"
    "Answer with line numbers only: single numbers or ranges, separated by commas.\n"
    "For example: 1, 40-47, 512\n"
    "Write nothing else. Do not explain, do not quote any line, do not repeat the "
    "text. Only numbers."
)

QUESTION = (
    "You are given the numbered output of a command someone just ran.\n"
    "Choose the lines a person debugging this would need to see: what failed, "
    "what warned, what changed, the final result, and the few lines around them "
    "that make those readable.\n"
    "Leave out repetition, progress that only says work happened, and lines that "
    "carry no information on their own.\n" + ANSWER_FORMAT
)

# One ask covers this much of the transcript. Most captures fit in a single one;
# a long build is split and the answers are added together.
CHARS_PER_ASK = 120_000

# Only in the prompt. A line thousands of characters wide is nearly always
# machine noise, and the model needs its beginning to judge it, not all of it.
# What gets shown is never shortened -- that comes from the file.
PROMPT_LINE_CAP = 400

# Ranges written the way a model writes them: a hyphen, or one of the dashes a
# text generator reaches for instead (U+2013, U+2014). Escaped rather than typed
# so that a dash nobody can see in a diff cannot go missing from here.
_NUMBERS = re.compile(r"(\d+)\s*[-\u2013\u2014]\s*(\d+)|(\d+)")


@dataclass(frozen=True)
class View:
    """A capture with most of it folded away, and a note of what was folded."""

    handle: str
    text: str
    kept: int
    total: int
    model: str | None
    asks: int

    @property
    def folded(self) -> int:
        return self.total - self.kept


def numbered(lines: list[str], first: int = 1, cap: int = PROMPT_LINE_CAP) -> str:
    """The lines as the model sees them: one number, one bar, one line."""
    out = []
    for offset, line in enumerate(lines):
        shown = line if len(line) <= cap else line[:cap] + " …"
        out.append(f"{first + offset}| {shown}")
    return "\n".join(out)


def read_numbers(answer: str, total: int) -> set[int]:
    """Every line number in the model's reply, and nothing else from it.

    Prose around the numbers is ignored rather than rejected: a model that
    explains itself has still answered the question, and the explanation is the
    part that cannot be trusted. Numbers outside the capture are dropped -- a
    line that does not exist cannot be shown, and inventing one is exactly what
    this design exists to prevent.
    """
    chosen: set[int] = set()
    for low, high, single in _NUMBERS.findall(answer):
        if single:
            start = end = int(single)
        else:
            start, end = sorted((int(low), int(high)))
        start = max(start, 1)
        end = min(end, total)
        chosen.update(range(start, end + 1))
    return chosen


def runs(chosen: set[int]) -> list[tuple[int, int]]:
    """The chosen numbers as consecutive stretches, in order."""
    stretches: list[tuple[int, int]] = []
    for number in sorted(chosen):
        if stretches and number == stretches[-1][1] + 1:
            stretches[-1] = (stretches[-1][0], number)
        else:
            stretches.append((number, number))
    return stretches


def gap(count: int, handle: str) -> str:
    """The mark left where lines were folded away.

    It says how many, and how to read them. A view that hid things silently
    would be asking to be trusted; this one can be checked.
    """
    word = "line" if count == 1 else "lines"
    return f"─ {count:,} {word} not shown · sift peek {handle} for any of them ─"


def render(lines: list[str], chosen: set[int], handle: str) -> str:
    """The view: chosen lines exactly as captured, gaps marked with their size."""
    pieces: list[str] = []
    previous_end = 0
    for start, end in runs(chosen):
        if start > previous_end + 1:
            pieces.append(gap(start - previous_end - 1, handle))
        pieces.extend(lines[start - 1 : end])
        previous_end = end
    if previous_end < len(lines):
        pieces.append(gap(len(lines) - previous_end, handle))
    return "\n".join(pieces)


def select(
    lines: list[str],
    question: str,
    handle: str,
    bridge: Bridge | None = None,
) -> View | None:
    """Ask one question about numbered lines, and show the ones it answers with.

    The question is an argument because nothing underneath it is about failures.
    Numbering the lines, cutting a long text into asks that keep their original
    numbering, reading numbers out of a reply and discarding the rest, printing
    from the source byte for byte -- none of that changes when the question
    changes from *what went wrong here* to *what is declared here*. Only the
    sentence changes, and a second sentence is not a second engine.

    Returns nothing when there is no usable judgement -- no key, no model that
    would answer, or an answer with no numbers in it. The caller decides what to
    do with that; falling back is not this function's business, and pretending to
    have judged would be worse than admitting it did not.
    """
    if not lines:
        return View(handle, "", 0, 0, None, 0)

    judge = bridge if bridge is not None else Bridge()
    chosen: set[int] = set()
    model: str | None = None
    asks = 0

    for first, window in _windows(lines):
        answer = judge.ask(question, numbered(window, first), max_tokens=2048)
        asks += 1
        if answer is None:
            continue
        model = answer.model
        chosen |= read_numbers(answer.text, len(lines))

    if not chosen:
        return None
    return View(
        handle=handle,
        text=render(lines, chosen, handle),
        kept=len(chosen),
        total=len(lines),
        model=model,
        asks=asks,
    )


def distill(capture: Capture, bridge: Bridge | None = None) -> View | None:
    """Ask which lines of a capture matter, then show those lines from it."""
    return select(text_lines.of(capture.text()), QUESTION, capture.handle, bridge)


def _windows(lines: list[str]) -> list[tuple[int, list[str]]]:
    """The transcript in pieces small enough to ask about, each with its offset.

    Splitting keeps the original numbering: a window that starts at line 4,001 is
    numbered from 4,001, so an answer about it needs no translation and cannot be
    misread as being about the top of the file.
    """
    windows: list[tuple[int, list[str]]] = []
    start = 0
    size = 0
    for index, line in enumerate(lines):
        cost = min(len(line), PROMPT_LINE_CAP) + 12
        if size and size + cost > CHARS_PER_ASK:
            windows.append((start + 1, lines[start:index]))
            start = index
            size = 0
        size += cost
    windows.append((start + 1, lines[start:]))
    return windows
