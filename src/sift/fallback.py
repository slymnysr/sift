"""What to show when nobody could be asked.

There is no key, or no network, or the endpoint is busy, or the reply made no
sense. The command has already run and its output is already on disk. Something
has to be shown, and it has to be shown without a model.

The temptation here is to be clever: look for the word "error", recognise a
stack trace, score lines by how alarming they look. That is exactly the design
this project was rewritten to get rid of. Patterns like those are a list of
languages wearing a disguise -- they work for English and for the half-dozen
formats whoever wrote them happened to know, and they quietly fail for Turkish,
for Japanese, for a tool that shipped last week. Worse, they fail while looking
confident.

So this makes no claim about meaning at all. It shows the beginning and the end
and marks what it skipped. The beginning says what was run; the end says how it
came out. That is true of a compiler, a test runner, an installer, a shell
script, in every language a person or a machine writes in, and it needs to know
nothing about any of them.

It is worse than a model. It is meant to be. What it must never be is wrong, and
a rule that makes no claim cannot make a false one.
"""

from __future__ import annotations

from sift import lines as text_lines
from sift.capture import Capture
from sift.distill import View, render

# The first lines are usually the invocation and the first thing to go wrong.
HEAD = 10

# The last lines are the result: the summary, the exit, the reason. In every
# command-line tradition, the ending is where the answer lives.
TAIL = 40

# A run that failed says why near the end, and tends to say more of it: a
# traceback, a diagnostic, a list of what did not build.
TAIL_WHEN_FAILED = 80


def ends(total: int, *, head: int = HEAD, tail: int = TAIL) -> set[int]:
    """The first `head` and the last `tail` lines, or all of them if that is fewer."""
    if total <= head + tail:
        return set(range(1, total + 1))
    return set(range(1, head + 1)) | set(range(total - tail + 1, total + 1))


def fallback(capture: Capture) -> View:
    """A view built without asking anything, and honest about being one.

    `model` is left empty, which is how the caller can tell this apart from a
    view a model chose. A reader who is told which lines were picked, and by
    what, can decide whether to go and read the rest.
    """
    lines = text_lines.of(capture.text())
    total = len(lines)
    if not total:
        return View(capture.handle, "", 0, 0, None, 0)

    tail = TAIL_WHEN_FAILED if capture.meta.failed else TAIL
    chosen = ends(total, head=HEAD, tail=tail)
    return View(
        handle=capture.handle,
        text=render(lines, chosen, capture.handle),
        kept=len(chosen),
        total=total,
        model=None,
        asks=0,
    )
