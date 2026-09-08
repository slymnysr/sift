"""When a line is not a unit anybody can choose.

Everything else here counts in lines, and for command output that is right: a
line is what the writer meant as one thing and what a reader's eye stops on.

A JSON array is the case where it is simply false. Written by a machine for
another machine, it very often has no newlines at all -- four hundred kilobytes
on line 1 -- and then there is exactly one unit to choose from and choosing it
means showing all of it. Written out with indentation it is worse in a quieter
way: the lines exist, but a line of one is `"id": 3,`, which is true, chosen,
byte for byte from the file, and of no use to anybody. Neither shape is helped
by a better question. The unit is wrong.

So when the text is a JSON array, the record is the unit and everything else
stays exactly as it was. The model still answers with numbers and nothing else,
the text still comes out of the source unchanged, and a gap still says how many
of them it covers. Only what is being counted changes.

**Nothing is re-serialised.** A record is a slice of the original text, offset
to offset, so the whitespace, key order and number formatting a reader sees are
the ones in the file. Handing back `json.dumps` of a parsed value would be this
tool writing a line, which is the one thing it does not do -- and it would be
wrong quietly: `1.0` comes back `1.0`, but `1E2` comes back `100.0`.

**Only a top-level array.** An object wrapping one (`{"results": [...]}`) is
left as lines, and that is a decision rather than an omission: picking which of
an object's arrays holds "the records" is a guess about somebody else's schema,
and a guess that decides what a reader sees is the thing this project was
rewritten to be rid of. A caller who knows better has `--keep`.
"""

from __future__ import annotations

import json

# One record is not a choice, and a view of it is the text itself. Below two,
# lines are no worse and the machinery is not worth entering.
FEWEST = 2

_SPACE = " \t\n\r"


def of(text: str) -> list[str] | None:
    """The records of a top-level JSON array, or None if that is not what this is.

    Each record is `text[start:end]` of the source. The scan is a single pass
    with the standard decoder, which is what makes it exact rather than a
    bracket-counter that a brace inside a string would fool.

    Returns None rather than raising, everywhere: this is asked of every capture
    and almost every one of them is not JSON. "No" is the ordinary answer here,
    not a failure, and it costs one character to reach.
    """
    at = _past_space(text, 0)
    if at >= len(text) or text[at] != "[":
        return None

    decoder = json.JSONDecoder()
    found: list[str] = []
    at = _past_space(text, at + 1)

    while True:
        if at >= len(text):
            return None  # the array never closed; this is not a whole document
        if text[at] == "]" and not found:
            return None  # an empty array has nothing to choose between
        try:
            _, end = decoder.raw_decode(text, at)
        except ValueError:
            return None
        found.append(text[at:end])

        at = _past_space(text, end)
        if at >= len(text):
            return None
        if text[at] == "]":
            break
        if text[at] != ",":
            return None
        at = _past_space(text, at + 1)

    # A document that goes on after the array is not an array. Refusing it keeps
    # the promise the rest of this file rests on: every byte of the source is in
    # exactly one record, so a count of records folded away is a count of the
    # whole thing.
    if _past_space(text, at + 1) != len(text):
        return None
    return found if len(found) >= FEWEST else None


def _past_space(text: str, at: int) -> int:
    """The next index at or after `at` that is not JSON whitespace."""
    while at < len(text) and text[at] in _SPACE:
        at += 1
    return at
