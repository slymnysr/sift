"""The MCP server: the same three answers, handed to a model instead of a person.

This is where the tool actually pays. At a terminal a shortened view saves
someone some scrolling. Over MCP it saves the caller's context window, and a
tool result is re-sent with every turn that follows it -- so a 5,000-line build
log kept out of the transcript is not paid for once and forgotten, it goes on
not being paid for the rest of the conversation.

Nothing here decides anything. Every tool calls the function the command line
calls, through the same ladder in `view.py`, so there is no second answer that
could be wrong on its own. What this module owns is the tool contract -- the
names, the parameters and the descriptions, which are the only documentation the
calling model ever reads -- and one thing the command line never has to think
about:

The footer has to move. `sift run` writes it to stderr, where the person sees
it. A client sees no stderr. Dropped, the caller cannot tell a view that a model
chose from the ends of a file shown because no model answered -- and would
believe the first when it was the second. So it travels inside the same string.
An error travels the same way, as text rather than as a raised exception: a tool
that raises hands the model nothing, and the third rule does not stop being true
because the reader is a machine.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from sift import __version__
from sift.capture import run as run_command
from sift.peek import peek as peek_at
from sift.view import (
    best_outline,
    best_view,
    footer,
    outline_footer,
    peek_footer,
)

INSTRUCTIONS = """\
Use `run` in place of a plain shell tool whenever a command may print more than
a few dozen lines: test suites, builds, installers, log tails, recursive greps.
It runs the command, keeps every byte on disk, and returns only the lines that
mattered, plus a handle for everything it left out.

Nothing in a result was written by a model. A judge is only ever asked which
line numbers matter; the text is printed from the local file byte for byte, so a
line you are shown is a line that was there. Every gap says how many lines stand
in it, and `peek` brings any of them back unchanged.

`outline` is that same question asked about a file instead of a command: what
does this file declare, without its bodies. It holds no list of languages and
never looks at the suffix, so it can be asked about anything.

The last line of every result says what you are looking at -- including whether
a model chose the lines or none could be reached.
"""

server = MCPServer(
    name="sift",
    version=__version__,
    instructions=INSTRUCTIONS,
)


@server.tool(
    name="run",
    description=(
        "Run a shell command and return only the lines that mattered instead of all "
        "of its output. Every byte is kept on disk and never enters the conversation, "
        "so a 5,000-line test run costs a few dozen lines of context -- and goes on "
        "costing nothing on every later turn, because tool results are re-sent with "
        "the rest of the transcript. The lines shown are the command's own, byte for "
        "byte; each gap states how many lines it stands for, and `peek` with the "
        "returned handle brings any range back in full. Prefer this over a plain "
        "shell tool whenever the output may be long or noisy."
    ),
)
def run(command: str, timeout: float | None = None) -> str:
    """Run `command` and return the lines that mattered.

    Args:
        command: The command line. It is handed to the shell, so pipes, globs and
            `&&` work the way they would if you had typed them.
        timeout: Give up after this many seconds. Left unset, the command runs to
            its own end. A command that is killed still returns what it printed
            first, and the last line says it timed out.
    """
    try:
        capture = run_command([command], shell=True, timeout=timeout)
    except OSError as exc:
        return f"sift: {exc}"
    view, who = best_view(capture)
    return _answer(view.text, footer(capture, view, who))


@server.tool(
    name="outline",
    description=(
        "Return what a file declares -- its types, functions, exports, targets and "
        "settings -- without their bodies, so that reading a 2,000-line source file "
        "costs a page. This is the machine behind `run` asked a different question: "
        "it holds no table of languages and never reads the suffix, so it answers "
        "about Rust, Haskell, a Makefile, a config file with no extension, or a "
        "language that did not exist last year. Lines come from the file byte for "
        "byte, and `peek` on the same path returns any range of it in full."
    ),
)
def outline(path: str) -> str:
    """Return what the file at `path` declares.

    Args:
        path: The file to read. Any language, any name, no extension needed.
    """
    try:
        view, who = best_outline(path)
    except OSError as exc:  # the file cannot be read; there is no view to give
        return f"sift: {exc}"
    return _answer(view.text, outline_footer(path, view, who))


@server.tool(
    name="peek",
    description=(
        "Return the exact original lines of a capture or a file, byte for byte, with "
        "the line numbers they had there. Use it with the handle at the end of a "
        "`run` result, or with any path, to open up a gap that a view left behind. "
        "A range reaching past the end is clamped rather than refused, and with no "
        "range at all it returns the whole thing."
    ),
)
def peek(handle: str, first: int | None = None, last: int | None = None) -> str:
    """Return lines `first` to `last` of a capture or a file, unchanged.

    Args:
        handle: A handle from a `run` result, or the path to a file.
        first: The first line to return, counting from 1. Unset means the start.
        last: The last line to return. Unset means the end.
    """
    try:
        found = peek_at(handle, first, last)
    except (OSError, ValueError) as exc:
        return f"sift: {exc}"
    return _answer(found.text, peek_footer(found))


def _answer(text: str, note: str) -> str:
    """The view and the line that says what it is, as one string.

    Joined rather than returned side by side because a client shows one block of
    text per call, and a note that arrives anywhere else does not arrive.
    """
    return f"{text}\n\n{note}" if text else note


def main() -> None:
    """Console-script entry point: serve over stdio."""
    server.run("stdio")


if __name__ == "__main__":
    main()
