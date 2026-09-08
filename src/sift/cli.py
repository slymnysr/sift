"""The command line: run something, read what mattered, go and read the rest.

Five commands that do something, because each one is a promise that has to keep
working in every language and every shell -- and two that report on them:

    sift run -- pytest -q          run it, show the lines that mattered
    sift run --background -- make  start it, get the prompt back
    sift follow a3f1               what it has said since you last looked
    sift stop a3f1                 end it, and write down how it ended
    sift outline src/parser.rs     what a file declares, without its bodies
    sift peek a3f1 200 260         the capture itself, byte for byte
    sift list                      what is running, and what has been run
    sift stats                     what the shortening cost, and what it saved

`outline` is the same machine asking a different question. Nothing in it knows
one language from another, and there is no list of suffixes deciding what it
will look at: the command word already said what you wanted.

The arguments are read by hand rather than with `argparse`. This is not
stubbornness: `sift run -- pytest -x --lf` hands `sift` a command that has flags
of its own, and any parser clever enough to be helpful is clever enough to eat
them. Everything after the command word is passed through untouched.

The rule this file exists to keep is the third one in the README: **nothing can
break your command.** No key, no network, a busy endpoint, a reply full of
nonsense, a bug in the distiller -- every one of them ends with the output on
screen and the command's own exit code coming back out. The model is an
improvement on this tool's behaviour, never a requirement of it.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time

from sift import store
from sift.background import alive, launch, seen, stop, unread, wait_for
from sift.capture import Capture, run
from sift.distill import BUDGET
from sift.hook import answer as hook_answer
from sift.memory import habits, reach
from sift.peek import FOUND_CAP, peek
from sift.tools import BY_NAME, KNOWN, command_for
from sift.view import (
    best_digest,
    best_digests,
    best_follow,
    best_outline,
    best_view,
    ending,
    follow_footer,
    footer,
    outline_footer,
    peek_footer,
    state,
)

USAGE = """sift -- run a command, keep every byte, show the lines that matter

  sift run [--timeout SECONDS] [--shell] [--background] [--cwd DIR]
           [--budget LINES] [--keep PATTERN] [--] COMMAND...
  sift follow [HANDLE] [--all] [--wait SECONDS]
  sift stop [HANDLE]
  sift outline [--budget LINES] [--keep PATTERN] PATH
  sift digest [--budget LINES] [--keep PATTERN] PATH...
  sift peek HANDLE|PATH [FIRST] [LAST] [--grep PATTERN] [--around N] [--max N]
  sift list [COUNT]
  sift hook                           answer one shell-command event on stdin
  sift tools                          which dense tools this machine has
  sift tool NAME [ARGS...]            run one of them, distilled
  sift memory [TERM] [--here]
  sift stats [COUNT]

Everything after COMMAND is passed to it unchanged. Use -- when the command
has flags that look like sift's own.

--keep shows every line matching PATTERN whatever else was chosen, and whatever
the budget says. It is your pattern, not one this tool guessed at."""

# What a shell reports when a command was killed for running too long, and what
# `timeout(1)` returns. Borrowed rather than invented: scripts already know it.
TIMED_OUT = 124

# What a shell reports when the command could not be found or could not be run.
CANNOT_RUN = 127


def main(argv: list[str] | None = None) -> int:
    _speak_utf8()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    word, rest = args[0], args[1:]
    if word == "run":
        return _run(rest)
    if word == "follow":
        return _follow(rest)
    if word == "stop":
        return _stop(rest)
    if word == "outline":
        return _outline(rest)
    if word == "digest":
        return _digest(rest)
    if word == "peek":
        return _peek(rest)
    if word == "list":
        return _list(rest)
    if word == "hook":
        return _hook()
    if word == "tools":
        return _tools()
    if word == "tool":
        return _tool(rest)
    if word == "memory":
        return _memory(rest)
    if word == "stats":
        return _stats(rest)
    print(f"sift: no such command: {word}\n\n{USAGE}", file=sys.stderr)
    return 2


def _speak_utf8() -> None:
    """Say what the command said, whatever the console was set up to expect.

    A capture can hold any language, and the gap marker is drawn with `─` and
    `·`. A console still set to a legacy code page -- the default on Windows --
    raises on the first character it cannot encode, which would lose the output
    to a detail of the terminal rather than anything about the command. Encoding
    with replacement loses a glyph; not doing this loses the run.
    """
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, OSError, ValueError):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _run(args: list[str]) -> int:
    timeout: float | None = None
    shell = False
    detached = False
    where: str | None = None
    budget: int | None = None
    keep: str | None = None
    while args:
        if args[0] == "--timeout" and len(args) > 1:
            timeout = _seconds(args[1])
            args = args[2:]
        elif args[0] == "--cwd" and len(args) > 1:
            where = args[1]
            args = args[2:]
        elif args[0] == "--budget" and len(args) > 1:
            budget = _line_number(args[1])
            args = args[2:]
        elif args[0] == "--keep" and len(args) > 1:
            keep = args[1]
            args = args[2:]
        elif args[0] == "--shell":
            shell = True
            args = args[1:]
        elif args[0] == "--background":
            detached = True
            args = args[1:]
        elif args[0] == "--":
            args = args[1:]
            break
        else:
            break

    if not args:
        print(f"sift: run needs a command\n\n{USAGE}", file=sys.stderr)
        return 2

    if detached:
        return _background(args, shell=shell, timeout=timeout, cwd=where)

    try:
        capture = run(args, timeout=timeout, shell=shell, cwd=where)
    except OSError as exc:
        print(f"sift: {exc}", file=sys.stderr)
        return CANNOT_RUN

    try:
        _show(capture, budget, keep)
    except Exception as exc:  # the view is optional; the output is not
        print(f"sift: {type(exc).__name__}: {exc}", file=sys.stderr)
        _last_resort(capture)
    return _exit_code(capture)


def _background(
    command: list[str], *, shell: bool, timeout: float | None, cwd: str | None = None
) -> int:
    """Start the command, say where to find it, and give the prompt back.

    The handle goes to stdout on its own so it can be caught in a variable; the
    advice goes to stderr with everything else this tool says about itself.

    A timeout is refused rather than ignored. There is nobody here to enforce
    one -- the point of this flag is that nothing waits -- and quietly dropping
    a limit the caller asked for is how a build runs all night.
    """
    if timeout is not None:
        print(
            "sift: --background and --timeout do not go together: nothing is waiting"
            f" to enforce it. Use sift stop when you have seen enough.\n\n{USAGE}",
            file=sys.stderr,
        )
        return 2

    try:
        started = launch(command, shell=shell, cwd=cwd)
    except OSError as exc:
        print(f"sift: {exc}", file=sys.stderr)
        return CANNOT_RUN

    print(started.handle)
    print(
        f"sift {started.handle} · started · sift follow {started.handle}",
        file=sys.stderr,
    )
    return 0


def _follow(args: list[str]) -> int:
    """What a running command has said since the last look, and nothing before it.

    With no handle it follows the newest run left going, which is what somebody
    who started one thing and walked away actually wants to type.
    """
    everything = "--all" in args
    args = [word for word in args if word != "--all"]
    wait = 0.0
    if len(args) > 1 and args[0] == "--wait":
        wait = _seconds(args[1]) or 0.0
        args = args[2:]
    elif len(args) > 2 and args[1] == "--wait":
        wait = _seconds(args[2]) or 0.0
        args = args[:1]

    if everything:
        return _follow_all(wait)

    handle = args[0] if args else _newest()
    if handle is None:
        print("sift: nothing is running", file=sys.stderr)
        return 1

    if wait:
        wait_for(handle, wait)

    running = store.load_running(handle)
    meta = store.load(handle)
    if running is None and meta is None:
        print(f"sift: no such run: {handle}", file=sys.stderr)
        return 1

    fresh, first, moved = unread(handle)
    view = None
    try:
        view, who = best_follow(handle, fresh, first)
        if view.text:
            print(view.text)
    except Exception as exc:  # the view is optional; the output is not
        print(f"sift: {type(exc).__name__}: {exc}", file=sys.stderr)
        for number, line in enumerate(fresh, first):
            print(f"{number:>6}  {line}")
        who = f"no view ({type(exc).__name__})"

    # The cursor moves only after the lines have been printed, whichever way
    # they were printed. Marking them read before that would lose them for good
    # to a failure that has nothing to do with the command.
    seen(handle, moved)

    if view is not None:
        note = follow_footer(handle, view, who, first, state(running, meta))
        print(note, file=sys.stderr)
    if meta is not None and running is None:
        return _exit_code(Capture(meta))
    return 0


def _follow_all(wait: float = 0.0) -> int:
    """Every command still going, in one look.

    An agent supervising three builds should not have to ask three times and
    carry three answers. Waiting is done once, on whichever run speaks first,
    because waiting on each in turn would add their timeouts together.
    """
    running = store.started()
    if not running:
        print("sift: nothing is running", file=sys.stderr)
        return 1

    if wait:
        deadline = store.now() + wait
        while store.now() < deadline:
            if any(unread(r.handle)[0] for r in running):
                break
            time.sleep(0.1)

    for one in running:
        _follow([one.handle])
    return 0


def _stop(args: list[str]) -> int:
    """End a run and make sure it ends up with an ending written down."""
    handle = args[0] if args else _newest()
    if handle is None:
        print("sift: nothing is running", file=sys.stderr)
        return 1

    meta = stop(handle)
    if meta is None:
        print(f"sift: no such run: {handle}", file=sys.stderr)
        return 1
    print(
        f"sift {handle} · {ending(meta)} · {meta.byte_count:,} B captured"
        f" · sift follow {handle}",
        file=sys.stderr,
    )
    return 0


def _newest() -> str | None:
    found = store.started()
    return found[0].handle if found else None


def _show(capture: Capture, budget: int | None = None, keep: str | None = None) -> None:
    view, who = best_view(capture, BUDGET if budget is None else budget, keep)
    if view.text:
        print(view.text)
    print(footer(capture, view, who), file=sys.stderr)


def _last_resort(capture: Capture) -> None:
    """Everything that chooses lines has failed. Show every line instead.

    This is the floor the third rule stands on. Reaching it means `sift` has a
    bug, and a bug in the part that shortens output must cost the shortening --
    not the output, and not the exit code the caller is about to act on.
    """
    print(f"sift: showing the capture unchanged ({capture.handle})", file=sys.stderr)
    try:
        sys.stdout.write(capture.text())
    except OSError as exc:
        print(f"sift: the capture is at {store.raw_path(capture.handle)} ({exc})",
              file=sys.stderr)


def _exit_code(capture: Capture) -> int:
    """The command's own answer, so that wrapping it in `sift` changes nothing.

    A script that fails when `pytest` fails has to keep failing when it becomes
    `sift run -- pytest`. Anything else would make this tool unusable in the
    place it is most useful.
    """
    if capture.meta.timed_out:
        return TIMED_OUT
    return capture.meta.exit_code or 0


def _outline(args: list[str]) -> int:
    budget, keep, args = _shown_how(args)
    if not args:
        print(f"sift: outline needs a path\n\n{USAGE}", file=sys.stderr)
        return 2

    path = args[0]
    try:
        view, who = best_outline(path, budget, keep)
    except OSError as exc:  # the file itself cannot be read; there is no view
        print(f"sift: {exc}", file=sys.stderr)
        return 1

    if view.text:
        print(view.text)
    print(outline_footer(path, view, who), file=sys.stderr)
    return 0


def _digest(args: list[str]) -> int:
    """A file somebody else produced, read for what is in it.

    Shaped like `_outline` because it is the same machinery asked a different
    question, and the two must not drift: a caller who learns one has learned
    the other.
    """
    budget, keep, args = _shown_how(args)
    if not args:
        print(f"sift: digest needs a path\n\n{USAGE}", file=sys.stderr)
        return 2

    if len(args) == 1:
        try:
            view, who = best_digest(args[0], budget, keep)
        except OSError as exc:  # the file itself cannot be read; there is no view
            print(f"sift: {exc}", file=sys.stderr)
            return 1
        if view.text:
            print(view.text)
        print(outline_footer(args[0], view, who), file=sys.stderr)
        return 0

    # Several paths are asked about at the same time. Each keeps its own footer,
    # because a reader with four digests in front of them needs to know which
    # one they are looking at and which of them nobody could reach a model for.
    worst = 0
    for path, view, who in best_digests(args, budget, keep):
        if view.text:
            print(view.text)
        print(outline_footer(path, view, who), file=sys.stderr)
        if who.startswith("unreadable"):
            worst = 1
    return worst


def _shown_how(args: list[str]) -> tuple[int | None, str | None, list[str]]:
    """The two words a caller may put before a path, and what is left after them."""
    budget: int | None = None
    keep: str | None = None
    while len(args) > 1 and args[0] in ("--budget", "--keep"):
        if args[0] == "--budget":
            budget = _line_number(args[1])
        else:
            keep = args[1]
        args = args[2:]
    return budget, keep, args


def _peek(args: list[str]) -> int:
    grep: str | None = None
    around = 3
    cap = FOUND_CAP
    kept: list[str] = []
    while args:
        if args[0] == "--grep" and len(args) > 1:
            grep = args[1]
            args = args[2:]
        elif args[0] == "--around" and len(args) > 1:
            around = _line_number(args[1]) or 0
            args = args[2:]
        elif args[0] == "--max" and len(args) > 1:
            cap = _line_number(args[1]) or FOUND_CAP
            args = args[2:]
        else:
            kept.append(args[0])
            args = args[1:]
    args = kept

    if not args:
        print(f"sift: peek needs a handle\n\n{USAGE}", file=sys.stderr)
        return 2
    first = _line_number(args[1]) if len(args) > 1 else None
    last = _line_number(args[2]) if len(args) > 2 else None
    try:
        found = peek(args[0], first, last, grep, around, cap)
    except (OSError, ValueError) as exc:
        print(f"sift: {exc}", file=sys.stderr)
        return 1
    if found.text:
        print(found.text)
    print(peek_footer(found), file=sys.stderr)
    return 0


def _list(args: list[str]) -> int:
    """What is running, then what has been run.

    Running first because it is the part that can still be acted on. Their size
    is read off the file rather than from a record, since the record of how big
    a capture ended up is written when it ends.
    """
    limit = _line_number(args[0]) if args else None
    for running in store.started():
        path = store.raw_path(running.handle)
        size = path.stat().st_size if path.is_file() else 0
        state = "running" if alive(running) else "lost"
        print(f"{running.handle}  {state:>9}  {size:>10,} B  {' '.join(running.command)}")
    for meta in store.recent(limit or 20):
        written = " ".join(meta.command)
        print(f"{meta.handle}  {ending(meta):>9}  {meta.byte_count:>10,} B  {written}")
    return 0


def _hook() -> int:
    """Answer one shell-command event, read from stdin as JSON.

    Everything about this is written to fail open. Unreadable input, an
    unexpected shape, a bug underneath -- each of them prints an empty answer,
    which the client reads as *carry on*, and the command runs exactly as it
    would have. A gate that breaks a shell is worse than no gate.
    """
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except (OSError, ValueError):
        event = {}

    try:
        said = hook_answer(event)
    except Exception:  # the shell is not allowed to depend on this working
        said = {}

    print(json.dumps(said, ensure_ascii=False))
    return 0


def _tools() -> int:
    """What each of them replaces, and whether this machine has it.

    Nothing is installed from here. The list is a list of programs, not a
    dependency: a machine that has none of them runs everything else in this
    tool exactly as well.
    """
    for one in KNOWN:
        mark = "here" if one.here else "not here"
        print(f"  {one.name:<5} {mark:<9} {one.known_as:<12} replaces {one.replaces}")
    return 0


def _tool(args: list[str]) -> int:
    """Run one of the dense tools and show what mattered in what it printed.

    It is distilled like anything else, because that is the point: these
    commands answer a question without opening a file, and then print more than
    anyone can read.
    """
    if not args:
        print(f"sift: tool needs a name\n\n{USAGE}", file=sys.stderr)
        return 2

    line = command_for(args[0], args[1:])
    if line is None:
        known = ", ".join(one.name for one in KNOWN)
        print(f"sift: no such tool: {args[0]} (there is {known})", file=sys.stderr)
        return 2

    known = BY_NAME[args[0]]
    if not known.here:
        print(
            f"sift: {known.known_as} is not on this machine. It is what `{known.name}`"
            f" runs, and it replaces {known.replaces}.",
            file=sys.stderr,
        )
        return CANNOT_RUN

    try:
        capture = run(line)
    except OSError as exc:
        print(f"sift: {exc}", file=sys.stderr)
        return CANNOT_RUN

    try:
        _show(capture)
    except Exception as exc:  # the view is optional; the output is not
        print(f"sift: {type(exc).__name__}: {exc}", file=sys.stderr)
        _last_resort(capture)
    return _exit_code(capture)


def _memory(args: list[str]) -> int:
    """What has been run here before, and how it went.

    No model is asked. The question is counting, and a model asked to count is
    slower, costs a request and is sometimes wrong -- the same misuse as a rules
    engine deciding which lines matter, pointed the other way.
    """
    here = "--here" in args
    rest = [word for word in args if word != "--here"]
    term = rest[0] if rest else None

    found = habits(term, os.getcwd() if here else None)
    if not found:
        seen = reach()
        where = " here" if here else ""
        print(f"sift: nothing{where} matches that, out of {seen:,} runs still on disk.")
        return 0

    print(f"{'runs':>5}  {'failed':>6}  {'last':>9}  command")
    for one in found:
        mark = "  ← never worked here" if one.never_worked else ""
        print(
            f"{one.runs:>5}  {one.failures:>6}  {one.last_ending:>9}  {one.command}{mark}"
        )

    seen = reach()
    print(f"\nout of {seen:,} runs still on disk; a capture that was removed took its record")
    return 0


def _stats(args: list[str]) -> int:
    """What the shortening cost and what it saved, over the runs it was used on.

    Per run and then in total, because the two say different things. One run is
    a claim about one command; the total is the only number that answers the
    question somebody installing this actually has, which is whether the tool is
    worth the asks it spends.
    """
    limit = _line_number(args[0]) if args else None
    found = store.savings(limit or 20)
    if not found:
        print("sift: no view has been built yet, so there is nothing to add up.")
        return 0

    print(
        f"{'handle':8}  {'captured':>12}  {'shown':>10}  {'part':>6}"
        f"  {'asks':>4}  command"
    )
    raw = shown = 0
    for meta, saving in found:
        raw += saving.raw_bytes
        shown += saving.shown_bytes
        print(
            f"{saving.handle:8}  {saving.raw_bytes:>10,} B  {saving.shown_bytes:>8,} B"
            f"  {saving.part:>5.1f}%  {saving.asks:>4}  {' '.join(meta.command)}"
        )

    part = shown * 100 / raw if raw else 0.0
    word = "run" if len(found) == 1 else "runs"
    print(
        f"\n{len(found)} {word} · {raw:,} B captured · {shown:,} B shown"
        f" · {part:.1f}% of it · the other {100 - part:.1f}% is on disk, not gone"
    )
    return 0


def _seconds(written: str) -> float | None:
    try:
        return float(written)
    except ValueError:
        return None


def _line_number(written: str) -> int | None:
    try:
        return int(written)
    except ValueError:
        return None
