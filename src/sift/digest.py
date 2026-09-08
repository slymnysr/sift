"""A file someone already has, read for what happened in it.

Three questions now go to the same machinery. `distill` asks what mattered in a
command this tool just ran. `outline` asks what a source file declares. This
asks the third, and it is the one a caller reaches for most often without
noticing: *here is a file I did not produce and cannot afford to read whole --
what is in it?*

A build log written by CI last night. A test report attached to an issue. A
crash dump, a 40,000-line JSON export, the output of something that ran on
another machine entirely. None of these can be `run` again, and none of them are
source code, so neither of the first two questions fits.

The distinction from `outline` is not the file, it is the question. Asked of a
log, *what does this declare* returns nothing useful; asked of a Python module,
*what happened here* returns its imports. The caller knows which they are
holding, and the command word is where they say so -- exactly as it is for `run`
and `outline`.

What does not change: the file is opened here and its contents never enter the
conversation, the model answers with line numbers only, and every line shown is
printed from the file byte for byte. A 40,000-line log costs a screenful, and
the other 39,900 lines are one `sift peek` away because nothing was touched.
"""

from __future__ import annotations

from pathlib import Path

from sift import lines as text_lines
from sift import records
from sift.distill import BUDGET, RECORDS, View, select
from sift.fallback import from_lines
from sift.model import Bridge
from sift.outline import text_of

QUESTION = (
    "You are given a file, numbered by line. It is something that was already "
    "produced and saved -- a log, a build or test transcript, a crash dump, a "
    "report, an export -- and it is too long to read whole.\n"
    "Choose the lines someone would need to understand what is in it: what "
    "failed, what warned, what changed, what it concluded, the headings and "
    "boundaries that say where one part ends and the next begins, and the few "
    "lines around those that make them readable.\n"
    "Leave out repetition, progress that only says work happened, and lines that "
    "carry no information on their own.\n"
    "Nothing here is guaranteed to be at the end: a saved file may stop in the "
    "middle of whatever was writing it, so do not assume the last lines are the "
    "conclusion.\n"
)


def digest(
    path: str | Path,
    bridge: Bridge | None = None,
    budget: int | None = None,
    keep: str | None = None,
) -> View | None:
    """What is in `path`, chosen by a model and printed from the file.

    Handled by the path, like an outline, so the gap marker names the way back
    and `sift peek` takes it unchanged. Returns nothing when there was no usable
    judgement -- the same contract `distill` and `outline` keep, for the same
    reason: a view that pretended to have been chosen would be worse than one
    that admits it was not.
    """
    text = text_of(path)
    found = records.of(text)
    ceiling = BUDGET if budget is None else budget
    if found is not None:
        return select(
            found,
            RECORDS,
            str(path),
            bridge,
            budget=ceiling,
            keep=keep,
            unit="record",
        )
    return select(
        text_lines.of(text),
        QUESTION,
        str(path),
        bridge,
        budget=ceiling,
        keep=keep,
    )


def ends_of(path: str | Path) -> View:
    """What to show when nobody could be asked.

    The beginning of a log says what was being attempted and the end says how it
    came out, which is a better guess here than it is for source code and still
    only a guess. Every line it skips is counted and named.
    """
    text = text_of(path)
    found = records.of(text)
    if found is not None:
        return from_lines(found, str(path), unit="record")
    return from_lines(text_lines.of(text), str(path))
