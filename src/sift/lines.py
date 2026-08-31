"""What counts as a line.

`str.splitlines()` splits on more than anyone else does: form feed, vertical
tab, the file and group separators, NEL (U+0085), and the Unicode line and
paragraph separators (U+2028, U+2029). Every one of those turns up in real
command output. U+0085 comes out of EBCDIC conversions, which is how a mainframe
job log reaches a terminal. U+2028 comes out of tooling that pasted a string it
read from somewhere else. A form feed is how a good deal of older software
starts a new page.

When they turn up, a capture gains lines that nothing else agrees exist. `wc -l`
would not count them, the terminal did not show them, and `sift peek 40 50`
would answer with different text than the editor open beside it. For a tool
whose whole promise is that the line you were shown is the line that is there,
that is not a small disagreement.

So a line here ends at a newline, and at nothing else. A carriage return before
it belongs to the ending rather than to the content -- which is what a terminal
does with CRLF, and what every other tool means by a line.

A carriage return anywhere *else* is left exactly where it is. A progress bar
that redraws itself nine hundred times is one line in the terminal, and it is
one line here too, rather than nine hundred lines of a number counting up.
"""

from __future__ import annotations


def of(text: str) -> list[str]:
    """The lines of `text`, counted the way the rest of the world counts them."""
    if not text:
        return []
    found = text.split("\n")
    if found[-1] == "":
        # A trailing newline ends the last line; it does not begin another one.
        found.pop()
    return [line[:-1] if line.endswith("\r") else line for line in found]
