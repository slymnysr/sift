"""The command line: run something, read what mattered, go and read the rest.

Four commands and no more, because each one is a promise that has to keep
working in every language and every shell:

    sift run -- pytest -q          run it, show the lines that mattered
    sift outline src/parser.rs     what a file declares, without its bodies
    sift peek a3f1 200 260         the capture itself, byte for byte
    sift list                      what has been run lately

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
import sys

from sift import store
from sift.capture import Capture, run
from sift.distill import View, distill
from sift.fallback import fallback
from sift.model import Bridge
from sift.outline import ends_of, outline
from sift.peek import peek

USAGE = """sift -- run a command, keep every byte, show the lines that matter

  sift run [--timeout SECONDS] [--shell] [--] COMMAND...
  sift outline PATH
  sift peek HANDLE|PATH [FIRST] [LAST]
  sift list [COUNT]

Everything after COMMAND is passed to it unchanged. Use -- when the command
has flags that look like sift's own."""

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
    if word == "outline":
        return _outline(rest)
    if word == "peek":
        return _peek(rest)
    if word == "list":
        return _list(rest)
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
    while args:
        if args[0] == "--timeout" and len(args) > 1:
            timeout = _seconds(args[1])
            args = args[2:]
        elif args[0] == "--shell":
            shell = True
            args = args[1:]
        elif args[0] == "--":
            args = args[1:]
            break
        else:
            break

    if not args:
        print(f"sift: run needs a command\n\n{USAGE}", file=sys.stderr)
        return 2

    try:
        capture = run(args, timeout=timeout, shell=shell)
    except OSError as exc:
        print(f"sift: {exc}", file=sys.stderr)
        return CANNOT_RUN

    try:
        _show(capture)
    except Exception as exc:  # the view is optional; the output is not
        print(f"sift: {type(exc).__name__}: {exc}", file=sys.stderr)
        _last_resort(capture)
    return _exit_code(capture)


def _show(capture: Capture) -> None:
    view, who = _view(capture)
    if view.text:
        print(view.text)
    print(_footer(capture, view, who), file=sys.stderr)


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


def _view(capture: Capture) -> tuple[View, str]:
    """The best view available, and a word about where it came from.

    Every failure below lands in the same place: the ends of the capture, shown
    without a model. That is the whole safety net -- there is no path out of
    this function that does not return something to read.
    """
    bridge = Bridge()
    reason = "no model"
    try:
        chosen = distill(capture, bridge)
        if chosen is not None:
            return chosen, chosen.model or "model"
        reason = bridge.last_error or "no lines chosen"
    except Exception as exc:  # a bug here must not cost the user their output
        reason = f"{type(exc).__name__}: {exc}"
    return fallback(capture), f"no model ({reason})"


def _footer(capture: Capture, view: View, who: str) -> str:
    """One line telling the reader what they are looking at, and what they are not."""
    meta = capture.meta
    ending = "timed out" if meta.timed_out else f"exit {meta.exit_code}"
    return (
        f"sift {capture.handle} · {ending} · {view.kept:,}/{view.total:,} lines"
        f" · {who} · {meta.duration_s:.1f}s"
    )


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
    if not args:
        print(f"sift: outline needs a path\n\n{USAGE}", file=sys.stderr)
        return 2

    path = args[0]
    try:
        view, who = _outline_view(path)
    except OSError as exc:  # the file itself cannot be read; there is no view
        print(f"sift: {exc}", file=sys.stderr)
        return 1

    if view.text:
        print(view.text)
    print(
        f"sift {path} · {view.kept:,}/{view.total:,} lines · {who}",
        file=sys.stderr,
    )
    return 0


def _outline_view(path: str) -> tuple[View, str]:
    """The best outline available, and a word about where it came from.

    Shaped like `_view` and for the same reason: every way of failing to ask a
    model ends at the ends of the file rather than at an error. The one failure
    that is allowed through is the file being unreadable, because then there is
    nothing to show and saying so is the only honest answer.
    """
    bridge = Bridge()
    reason = "no model"
    try:
        chosen = outline(path, bridge)
        if chosen is not None:
            return chosen, chosen.model or "model"
        reason = bridge.last_error or "no lines chosen"
    except OSError:
        raise
    except Exception as exc:  # a bug here must not cost the user their outline
        reason = f"{type(exc).__name__}: {exc}"
    return ends_of(path), f"no model ({reason})"


def _peek(args: list[str]) -> int:
    if not args:
        print(f"sift: peek needs a handle\n\n{USAGE}", file=sys.stderr)
        return 2
    first = _line_number(args[1]) if len(args) > 1 else None
    last = _line_number(args[2]) if len(args) > 2 else None
    try:
        found = peek(args[0], first, last)
    except (OSError, ValueError) as exc:
        print(f"sift: {exc}", file=sys.stderr)
        return 1
    if found.text:
        print(found.text)
    print(
        f"sift {found.handle} · lines {found.first_line:,}-{found.last_line:,}"
        f" of {found.total_lines:,}",
        file=sys.stderr,
    )
    return 0


def _list(args: list[str]) -> int:
    limit = _line_number(args[0]) if args else None
    for meta in store.recent(limit or 20):
        ending = "timed out" if meta.timed_out else f"exit {meta.exit_code}"
        written = " ".join(meta.command)
        print(f"{meta.handle}  {ending:>9}  {meta.byte_count:>10,} B  {written}")
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
