"""What a file declares, without its bodies.

A log is read for what went wrong; a source file is read for what is in it and
where. Those are two questions. `distill` answers the first. This asks the
second -- of the same model, through the same machinery, under the same
guarantee: the answer is a set of line numbers, and every line shown is printed
from the file byte for byte.

The design this replaces was a table. One entry per language, each holding
regular expressions for what a declaration looks like there, plus the suffixes
and the bare filenames that language claims. It ran to a thousand lines, covered
eighty-odd languages, and was still missing the next one. Its own comment
admitted the shape of the problem: *the rules are shapes, not grammars.* A
signature is only usually the line a language spends its keywords on, and
usually is a word that fails in front of a user.

There is no table here, and nothing in this file knows one language from
another. A model that can read Rust can also read the Zig that shipped last
week, the internal DSL nobody outside one company has seen, and the Makefile
with no extension at all. Being wrong is still possible -- the wrong lines can
be chosen -- but the cost of that mistake is a line missing from an outline,
never a line that says something the file does not say. And a missing line is
one `sift peek` away, because the file was never touched.
"""

from __future__ import annotations

from pathlib import Path

from sift import lines as text_lines
from sift.distill import View, select
from sift.fallback import from_lines
from sift.model import Bridge

# An outline is a table of contents, and a table of contents that runs past a
# screen has stopped being one.
#
# The number is stated here and spent by `select`, which divides it across
# however many asks the file takes and hands an over-long answer back rather than
# cutting it. Cutting here is what this module cannot do: deciding which
# declarations matter least means knowing what "nested" looks like, which is
# indentation in one language, braces in the next, and neither in the one after
# -- the guess this file exists to avoid. Asked again, the model does the ranking
# it is the only one here able to do; and an outline that comes back long anyway
# is visible, because the view says how many lines it kept out of how many.
BUDGET = 120

QUESTION = (
    "You are given a file, numbered by line.\n"
    "Choose the lines where the file declares something: where it names a thing "
    "it contains or offers -- a function, a type, a class, a constant, a target, "
    "a rule, a section, a setting -- together with any line that must be read "
    "with it to know what that thing is, such as a line that decorates or "
    "annotates the declaration, or that continues its signature.\n"
    "Leave out the bodies: the statements inside a definition, and anything that "
    "says how a thing works rather than that it exists.\n"
    "If more declarations qualify than the answer has room for, keep the "
    "outermost ones and leave the nested ones out.\n"
)


def read(path: str | Path) -> list[str]:
    """The lines of a file, counted the one way `sift` counts lines.

    Read as bytes and decoded here rather than through `Path.read_text`, which
    turns on universal newlines and would rewrite every carriage return into a
    line of its own. A file `sift` numbers has to be the file the editor beside
    it numbers, or every number in the outline points at different text.
    """
    return text_lines.of(Path(path).read_bytes().decode("utf-8", errors="replace"))


def outline(
    path: str | Path,
    bridge: Bridge | None = None,
    budget: int | None = None,
    keep: str | None = None,
) -> View | None:
    """The declarations in `path`, chosen by a model and printed from the file.

    The view is handled by the path itself, so the gap marker names the way back
    and `sift peek` will take it. Returns nothing when there is no usable
    judgement, exactly as `distill` does, and for the same reason: a view that
    pretended to have been chosen would be worse than one that admits it wasn't.

    The budget is passed rather than left to default, because a table of contents
    and a failing build are not the same length for the same reasons even when
    the number happens to match.
    """
    return select(
        read(path),
        QUESTION,
        str(path),
        bridge,
        budget=BUDGET if budget is None else budget,
        keep=keep,
    )


def ends_of(path: str | Path) -> View:
    """The outline to show when nobody could be asked.

    The first lines of a file and the last are a poor table of contents -- the
    top is usually a licence and the imports. They are not a wrong one, and
    every line they skip is counted and named.
    """
    return from_lines(read(path), str(path))
