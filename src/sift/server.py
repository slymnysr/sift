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

import time

try:
    from mcp.server.mcpserver import MCPServer
except ImportError as exc:
    # A sentence, not a stack. Installing `sift-cli` brings nothing with it on
    # purpose -- somebody who wants the command line should not be made to carry
    # a protocol library for it -- so arriving here is an ordinary thing to do
    # wrong, and the client that started this shows whatever comes out of it.
    raise SystemExit(
        "sift-mcp: the server half needs one more package.\n"
        "\n"
        '    uv tool install "sift-cli[mcp]"\n'
        "\n"
        "(or pipx. Plain `pip` is refused by Debian, Ubuntu and WSL, which\n"
        "protect the system Python -- and they are right to.)\n"
        "\n"
        "The command line (`sift`) is already installed and works without it."
    ) from exc


from sift import __version__, store
from sift.background import launch, seen, unread, wait_for
from sift.background import stop as stop_run
from sift.capture import run as run_command
from sift.distill import BUDGET
from sift.model import sending_on, somewhere_to_ask
from sift.peek import peek as peek_at
from sift.tools import BY_NAME, KNOWN, command_for
from sift.view import (
    best_digest,
    best_digests,
    best_follow,
    best_outline,
    best_view,
    follow_footer,
    footer,
    outline_footer,
    peek_footer,
    state,
)

# What a tool answers with when nobody has finished setting this up.
#
# The third rule says nothing here may break the caller's command, and that is
# why this is a sentence rather than an error, and why it says plainly that the
# command was not run. The caller has a shell of its own; the worst outcome is
# not "sift declined", it is "sift declined and the caller did not notice".
#
# Declining is not the same as failing open here, and the difference is which
# caller is reading. A person at a terminal can see a view built out of the ends
# of a file and judge it for what it is. A model cannot: it is handed a short
# text with a footer it has no reason to distrust, and a quietly worse answer is
# the one thing this project will not hand a reader who cannot check it.
NO_KEY = """\
sift is not set up on this machine, so it did nothing and ran nothing.

Run the command with your own shell tool instead. Nothing is in the way.

sift asks a free NVIDIA model which lines of an output matter. That needs a key,
and it has to be yours -- one is not shipped and one cannot be shared. Put it in
any of these and restart this server:

    SIFT_API_KEY=...            (environment)
    NVIDIA_API_KEY=...          (environment)
    ~/.config/nvidia/api_key    (a file with the key in it)

A key is free at https://build.nvidia.com

If you meant to run without a model, set SIFT_NO_MODEL=1 and sift will work
without asking anything -- deterministically, and less well.\
"""


def _unset() -> bool:
    """Whether this is a sift nobody finished setting up.

    Deliberately not the same question as "can a model be reached". Three states
    are worth telling apart and only one of them is this:

    * `SIFT_NO_MODEL=1` -- switched off on purpose. That is a decision, it is
      respected, and warning about it would be nagging somebody about a thing
      they typed.
    * no key at all -- nobody finished installing this. Nothing works as
      advertised and saying so is the only useful thing to do.
    * a key that the endpoint would not take, or an endpoint that is down --
      the third rule's territory, and it falls back to the ends of the output.
    """
    return sending_on() and not somewhere_to_ask()


INSTRUCTIONS = """\
Use `run` in place of a plain shell tool whenever a command may print more than
a few dozen lines: test suites, builds, installers, log tails, recursive greps.
It runs the command, keeps every byte on disk, and returns only the lines that
mattered, plus a handle for everything it left out.

Nothing in a result was written by a model. A judge is only ever asked which
line numbers matter; the text is printed from the local file byte for byte, so a
line you are shown is a line that was there. Every gap says how many lines stand
in it, and `peek` brings any of them back unchanged.

For a command with no natural end -- a dev server, a log tail, a build you want
to keep working during -- call `run` with `background` set. It returns a handle
straight away, and `follow` returns only what the command has printed since the
last time you asked, with the line numbers it has in the whole run. Nothing is
shown to you twice. When you are finished with one, call `follow` with `stop`
set: it ends the command, its children with it, and hands you the last of the
output.

`outline` is that same question asked about a file instead of a command: what
does this file declare, without its bodies. It holds no list of languages and
never looks at the suffix, so it can be asked about anything.

`digest` is the third question, and the one to reach for with a file you did not
produce: a log, a saved CI transcript, a crash dump, a long export. It asks what
happened in the file rather than what the file declares. Never read one of those
with a plain file-reading tool -- the whole thing lands in the conversation and
stays there. `digest_many` is the same for several files at once, and it is
worth reaching for whenever there is more than one: the waiting happens in
parallel and the answer is one tool result instead of four.

`tool` runs one of three dense programs -- `sg` (ast-grep), `diff`
(difftastic), `loc` (scc) -- and distils what it printed. Each of them answers a
question without opening a file, which is the cheapest way to answer anything:
reach for `sg` rather than reading candidate files to find where a shape occurs.

Two habits make all of this cheaper. Ask about several things in one call rather
than several calls -- `digest_many`, and `follow` with `everything` -- because
every tool result is re-sent on every later turn, so four answers cost four times
as much as one for the rest of the conversation. And when you are waiting on a
background command, pass `wait` rather than asking again in a moment: an answer
that says nothing happened costs the same as one that says something did.

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
        "shell tool whenever the output may be long or noisy. When you already know "
        "what you are looking for -- a symbol, a test name, an error code -- pass it "
        "as `keep` and every line containing it comes back whatever else was chosen."
    ),
)
def run(
    command: str,
    timeout: float | None = None,
    background: bool = False,
    cwd: str | None = None,
    budget: int | None = None,
    keep: str | None = None,
) -> str:
    """Run `command` and return the lines that mattered.

    Args:
        command: The command line. It is handed to the shell, so pipes, globs and
            `&&` work the way they would if you had typed them.
        timeout: Give up after this many seconds. Left unset, the command runs to
            its own end. A command that is killed still returns what it printed
            first, and the last line says it timed out.
        background: Start the command and return a handle instead of waiting for
            it. Use this for anything that does not end on its own -- a dev
            server, a log tail -- and for a long build you want to keep working
            during. Read it with `follow`, and end it with `follow` and `stop`.
        cwd: The directory to run in. Left unset, the server's own.
        budget: How many lines the view may cost. Left unset, a measured default
            that suits most output. Raise it when you need more of a long run,
            lower it when you only want the shape of one.
        keep: A regular expression. Every line matching it is in the view,
            whatever was chosen and whatever the budget says -- it is your
            pattern, not a guess this tool made. Text that is not a valid
            expression is searched for literally.
    """
    if _unset():
        return NO_KEY

    if background:
        return _start(command, timeout, cwd)
    try:
        capture = run_command([command], shell=True, timeout=timeout, cwd=cwd)
    except OSError as exc:
        return f"sift: {exc}"
    view, who = best_view(capture, BUDGET if budget is None else budget, keep)
    return _answer(view.text, footer(capture, view, who))


def _start(command: str, timeout: float | None, cwd: str | None = None) -> str:
    """Leave the command running, and say how to read it.

    A timeout is refused rather than quietly dropped: nothing is waiting here to
    enforce one, and a caller who believes a limit is in place when none is has
    been told something untrue about their own command.
    """
    if timeout is not None:
        return (
            "sift: timeout and background do not go together -- nothing is waiting to "
            "enforce it. Start it without a timeout and end it with follow(stop=true)."
        )
    try:
        started = launch([command], shell=True, cwd=cwd)
    except OSError as exc:
        return f"sift: {exc}"
    return (
        f"sift {started.handle} · started · nothing of its output has been shown yet."
        f" Read it with follow(handle=\"{started.handle}\")."
    )


@server.tool(
    name="follow",
    description=(
        "Return what a background command has printed since the last time you asked, "
        "and nothing you have already been shown. Use it with the handle from a "
        "`run` call made with `background`. The lines keep the numbers they have in "
        "the whole run, so `peek` on any of them returns that same line; a stretch "
        "that was only progress comes back as a gap saying how many lines it stands "
        "for, and a quiet minute comes back as nothing at all rather than as filler. "
        "Set `stop` when you are done with the command: it ends it, and everything "
        "it started, and returns the last of the output. Always stop a command you "
        "are finished with -- a background command left alone keeps running.\n"
        "With `everything` it answers about every run still going in one call, which "
        "is what to use when you started three things and want to know where they "
        "are. With `wait` it holds until something is actually said rather than "
        "coming back empty: an empty answer is a tool result that stays in the "
        "conversation for the rest of it, so waiting once costs less than asking "
        "five times."
    ),
)
def follow(
    handle: str | None = None,
    stop: bool = False,
    everything: bool = False,
    wait: float = 0.0,
) -> str:
    """Return what the run behind `handle` has said since the last look.

    Args:
        handle: The handle from a `run` call made with `background`. Leave it
            unset to follow the newest run.
        stop: End the command first, then return whatever it printed last. A run
            that has already finished is left alone; this is not an error.
        everything: Answer about every run still going, in one call, asked at the
            same time. `handle` and `stop` are ignored.
        wait: Hold for up to this many seconds for something new rather than
            answering that nothing has happened. A run that has already finished
            is never waited for.
    """
    if _unset():
        return NO_KEY

    if everything:
        return _every_run(wait)

    if handle is None:
        going = store.started()
        if not going:
            return "sift: nothing is running"
        handle = going[0].handle

    if wait and not stop:
        wait_for(handle, wait)

    if stop:
        stop_run(handle)
    running = store.load_running(handle)
    meta = store.load(handle)
    if running is None and meta is None:
        return f"sift: no such run: {handle}"

    fresh, first, moved = unread(handle)
    view, who = best_follow(handle, fresh, first)
    # Only once the lines are in the answer: a look that raised on the way here
    # is not a look the caller had, and the lines must still be theirs to ask for.
    seen(handle, moved)
    return _answer(view.text, follow_footer(handle, view, who, first, state(running, meta)))


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
def outline(path: str, budget: int | None = None, keep: str | None = None) -> str:
    """Return what the file at `path` declares.

    Args:
        path: The file to read. Any language, any name, no extension needed.
        budget: How many lines the outline may cost. Left unset, a length that
            keeps a table of contents to a screen.
        keep: A regular expression. Every line matching it is in the outline
            whatever else was chosen -- use it when you are looking for one
            declaration in a file too large to outline whole.
    """
    if _unset():
        return NO_KEY

    try:
        view, who = best_outline(path, budget, keep)
    except OSError as exc:  # the file cannot be read; there is no view to give
        return f"sift: {exc}"
    return _answer(view.text, outline_footer(path, view, who))


@server.tool(
    name="digest",
    description=(
        "Read a file and return a distilled view of what is in it instead of its "
        "text. This is for anything already written down that would flood the "
        "conversation if opened whole: a log, a saved build or CI transcript, a test "
        "report, a crash dump, a long JSON export. The server opens the file, so its "
        "contents never enter the conversation -- a 40,000-line log costs a screenful "
        "-- and every line shown is the file's own, byte for byte, with `peek` on the "
        "same path returning any range in full. Use `outline` instead when the file "
        "is source code and the question is what it declares."
    ),
)
def digest(path: str, budget: int | None = None, keep: str | None = None) -> str:
    """Return a distilled view of the file at `path`.

    Args:
        path: The file to read. Any format, any language, no extension needed.
        budget: How many lines the view may cost. Left unset, a measured default.
        keep: A regular expression. Every line matching it is in the view
            whatever else was chosen -- use it when you already know the error
            code, the test name or the timestamp you are looking for.
    """
    if _unset():
        return NO_KEY

    try:
        view, who = best_digest(path, budget, keep)
    except OSError as exc:  # the file cannot be read; there is no view to give
        return f"sift: {exc}"
    return _answer(view.text, outline_footer(path, view, who))




@server.tool(
    name="tool",
    description=(
        "Run one of three dense tools and return a distilled view of what it printed: "
        "`sg` (ast-grep) for structural search, `diff` (difftastic) for a diff that "
        "can tell a reindent from a change, `loc` (scc) for the size of a tree. Each "
        "of them answers a question *without opening the file* -- reach for `sg` "
        "instead of reading candidates to find where a shape occurs, and `loc` "
        "instead of listing a directory to size it. Their output is large by nature "
        "and is distilled like anything else, so a 4,000-line structural search costs "
        "a screenful with every byte still reachable through `peek`. A tool this "
        "machine does not have says so and says what it is called; nothing is "
        "installed for you."
    ),
)
def tool(name: str, args: list[str] | None = None) -> str:
    """Run the dense tool called `name` and return what mattered.

    Args:
        name: One of `sg`, `diff` or `loc`.
        args: What to pass it, as separate words.
    """
    if _unset():
        return NO_KEY

    line = command_for(name, list(args or []))
    if line is None:
        known = ", ".join(one.name for one in KNOWN)
        return f"sift: no such tool: {name} (there is {known})"

    known = BY_NAME[name]
    if not known.here:
        return (
            f"sift: {known.known_as} is not on this machine. It is what `{name}` runs,"
            f" and it replaces {known.replaces}."
        )

    try:
        capture = run_command(line)
    except OSError as exc:
        return f"sift: {exc}"
    view, who = best_view(capture)
    return _answer(view.text, footer(capture, view, who))


@server.tool(
    name="digest_many",
    description=(
        "Digest several files in one call, asked at the same time. Use it whenever "
        "there is more than one file to read: four logs cost four waits asked one by "
        "one and roughly one wait asked together, and come back as one tool result "
        "instead of four. Each file keeps its own last line saying which it is, and "
        "a file that cannot be read says so in its place rather than taking the "
        "others down with it."
    ),
)
def digest_many(paths: list[str], budget: int | None = None, keep: str | None = None) -> str:
    """Return a distilled view of each file in `paths`.

    Args:
        paths: The files to read, answered in the order given.
        budget: How many lines each view may cost.
        keep: A regular expression kept in every one of them.
    """
    if _unset():
        return NO_KEY

    if not paths:
        return "sift: digest_many needs at least one path"
    return "\n\n".join(
        _answer(built.text, outline_footer(path, built, who))
        for path, built, who in best_digests(paths, budget, keep)
    )

@server.tool(
    name="peek",
    description=(
        "Return the exact original lines of a capture or a file, byte for byte, with "
        "the line numbers they had there. Use it with the handle at the end of a "
        "`run` result, or with any path, to open up a gap that a view left behind. "
        "A range reaching past the end is clamped rather than refused, and with no "
        "range at all it returns the whole thing. With `grep` it searches instead: "
        "every line matching your pattern comes back with a few lines of context "
        "around it, which is the way into a gap when you know the word you want but "
        "not the line number."
    ),
)
def peek(
    handle: str,
    first: int | None = None,
    last: int | None = None,
    grep: str | None = None,
    around: int = 3,
    cap: int = 200,
) -> str:
    """Return lines `first` to `last` of a capture or a file, unchanged.

    Args:
        handle: A handle from a `run` result, or the path to a file.
        first: The first line to return, counting from 1. Unset means the start.
        last: The last line to return. Unset means the end.
        grep: A regular expression. Given one, `first` and `last` become the
            window to search rather than the answer, and every matching line
            comes back. Text that is not a valid expression is searched for
            literally.
        around: How many lines to show on each side of a match, so it can be
            read in context.
        cap: The most lines a search may return. Matches past it are left out
            and the last line says how many matched in total.
    """
    try:
        found = peek_at(handle, first, last, grep, around, cap)
    except (OSError, ValueError) as exc:
        return f"sift: {exc}"
    return _answer(found.text, peek_footer(found))


def _every_run(wait: float = 0.0) -> str:
    """Every command still going, in one answer.

    Three builds should not cost three tool calls and three results that stay in
    the transcript for the rest of the conversation. The waiting is done once, on
    whichever of them speaks first: waiting on each in turn would add their
    timeouts together and answer late about all of them.
    """
    going = store.started()
    if not going:
        return "sift: nothing is running"

    if wait:
        deadline = store.now() + wait
        while store.now() < deadline:
            if any(unread(one.handle)[0] for one in going):
                break
            time.sleep(0.1)

    return "\n\n".join(_one_run(one.handle) for one in going)


def _one_run(handle: str) -> str:
    """One run's slice, footer and all, ready to be put beside another's."""
    running = store.load_running(handle)
    meta = store.load(handle)
    if running is None and meta is None:
        return f"sift: no such run: {handle}"

    fresh, first, moved = unread(handle)
    built, who = best_follow(handle, fresh, first)
    seen(handle, moved)
    return _answer(built.text, follow_footer(handle, built, who, first, state(running, meta)))


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
