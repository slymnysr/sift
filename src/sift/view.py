"""What you are looking at, and where it came from.

Two front ends now ask the same question. The command line prints the view for a
person; the MCP server hands it to a model. Neither may keep its own copy of the
ladder that gets there -- a fallback that exists in one and not the other would
mean the third rule holds at the terminal and not over the wire, which is the
same as not holding at all.

So the ladder lives here, once, and both callers climb it. Every way of failing
to reach a model ends at the ends of the text rather than at an error, and there
is no path out of any function below that does not return something to read.

The lines that report on a view live here for the same reason. A view that does
not say a model was never reached is a view that claims one was, and that claim
has to be identical wherever it is made.

And what a view cost is written down here, on the way past, for a third time the
same reason: a saving measured at the terminal and not over the wire would be a
number about one caller published as a number about the tool.
"""

from __future__ import annotations

from collections.abc import Sequence

from sift import store
from sift.background import alive
from sift.capture import Capture
from sift.digest import digest
from sift.digest import ends_of as digest_ends
from sift.distill import BUDGET, View, distill, follow, render
from sift.fallback import fallback, from_lines
from sift.many import together
from sift.model import Bridge
from sift.outline import ends_of, outline
from sift.peek import Peek


def best_view(
    capture: Capture, budget: int | None = BUDGET, keep: str | None = None
) -> tuple[View, str]:
    """The best view of a capture, a word about where it came from, and the bill.

    A view built without a model is recorded too. It cost the caller whatever it
    cost them, and a report that counted only the good runs would be measuring
    the tool on its best days.
    """
    view, who = _choose(capture, budget, keep)
    store.record(
        store.Saving(
            handle=capture.handle,
            raw_bytes=capture.meta.byte_count,
            shown_bytes=len(view.text.encode("utf-8")),
            kept=view.kept,
            total=view.total,
            model=view.model,
            asks=view.asks,
            unanswered=view.unanswered,
        )
    )
    return view, who


def _choose(
    capture: Capture, budget: int | None = BUDGET, keep: str | None = None
) -> tuple[View, str]:
    """Every failure below lands in the same place: the ends of the capture,
    shown without a model. That is the whole safety net."""
    bridge = Bridge()
    reason = "no model"
    try:
        chosen = distill(capture, bridge, budget, keep)
        if chosen is not None:
            return chosen, chosen.model or "model"
        reason = bridge.last_error or "no lines chosen"
    except Exception as exc:  # a bug here must not cost the caller their output
        reason = f"{type(exc).__name__}: {exc}"
    return fallback(capture), f"no model ({reason})"


def best_follow(handle: str, lines: list[str], first: int) -> tuple[View, str]:
    """The best view of what a running command has said since the last look.

    Shaped like `best_view`, and different in the one way that matters: here an
    empty answer is an answer. A finished capture always has something worth
    showing -- what was run, how it ended -- so `distill` coming back with
    nothing means something went wrong and the ends are shown instead. But a
    minute of a build that printed nothing except progress genuinely has nothing
    in it worth a reader's attention, and saying so plainly is more use than
    showing forty lines of it to prove the tool is awake.

    The two are told apart by asking the bridge. A model that answered and named
    no lines leaves no error behind; a model that was never reached does.

    Nothing is recorded. A saving is a claim about a capture, and this is one
    look at a run still going: the run gets recorded when it ends, and counting
    every look as a capture of its own would inflate the only numbers this
    project publishes about itself.
    """
    if not lines:
        return View(handle, "", 0, 0, None, 0), "nothing new"

    bridge = Bridge()
    reason = "no model"
    try:
        chosen = follow(lines, handle, first, bridge)
        if chosen is not None:
            return chosen, chosen.model or "model"
        if bridge.last_error is None:
            return _quiet(lines, handle, first), "model (nothing new worth showing)"
        reason = bridge.last_error
    except Exception as exc:  # a bug here must not cost the caller their output
        reason = f"{type(exc).__name__}: {exc}"
    return from_lines(lines, handle, first=first), f"no model ({reason})"


def _quiet(lines: list[str], handle: str, first: int) -> View:
    """Lines a model read and chose none of: folded away, and counted as read.

    `model` is left empty even though a model was reached, because that field
    says which model's choice built this text and no text was built from one.
    What happened is told to the reader by the word that comes back beside it.
    """
    return View(
        handle=handle,
        text=render(lines, set(), handle, first),
        kept=0,
        total=len(lines),
        model=None,
        asks=1,
    )


def best_outline(
    path: str, budget: int | None = None, keep: str | None = None
) -> tuple[View, str]:
    """The best outline of a file, and a word about where it came from.

    Shaped like `best_view` and for the same reason. The one failure allowed
    through is the file being unreadable, because then there is nothing to show
    and saying so is the only honest answer.
    """
    bridge = Bridge()
    reason = "no model"
    try:
        chosen = outline(path, bridge, budget, keep)
        if chosen is not None:
            return chosen, chosen.model or "model"
        reason = bridge.last_error or "no lines chosen"
    except OSError:
        raise
    except Exception as exc:  # a bug here must not cost the caller their outline
        reason = f"{type(exc).__name__}: {exc}"
    return ends_of(path), f"no model ({reason})"


def footer(capture: Capture, view: View, who: str) -> str:
    """One line telling the reader what they are looking at, and what they are not."""
    meta = capture.meta
    return (
        f"sift {capture.handle} · {ending(meta)} · {counted(view)}"
        f" · {who} · {meta.duration_s:.1f}s" + silence(view)
    )


def best_digest(
    path: str, budget: int | None = None, keep: str | None = None
) -> tuple[View, str]:
    """The best view of a file somebody else produced, and where it came from.

    The third of the same shape, and deliberately identical to `best_outline`
    except for the question underneath. Two ladders that differed would mean a
    file read one way behaved differently from a file read the other, which is
    the sort of difference nobody finds until it matters.
    """
    bridge = Bridge()
    reason = "no model"
    try:
        chosen = digest(path, bridge, budget, keep)
        if chosen is not None:
            return chosen, chosen.model or "model"
        reason = bridge.last_error or "no lines chosen"
    except OSError:
        raise
    except Exception as exc:  # a bug here must not cost the caller their file
        reason = f"{type(exc).__name__}: {exc}"
    return digest_ends(path), f"no model ({reason})"


def best_digests(
    paths: Sequence[str], budget: int | None = None, keep: str | None = None
) -> list[tuple[str, View, str]]:
    """Several files, asked about at the same time, answered in the order given.

    The parallelism is worth having because the waiting is the whole cost: four
    files are four requests that sit in a socket, and sending them together
    turns four waits into one. What it does *not* do is send more at once than
    the machine was told to allow -- `distill.in_flight` sees to that, and this
    function deliberately does no arithmetic of its own about it.

    A file that could not be read comes back as the sentence about it rather
    than taking the other three down with it. One unreadable path in a list of
    four is not a reason to answer nothing.
    """
    def one(path: str):
        def ask() -> tuple[str, View, str]:
            try:
                built, who = best_digest(path, budget, keep)
            except OSError as exc:
                return path, View(path, "", 0, 0, None, 0), f"unreadable ({exc})"
            return path, built, who

        return ask

    return together([one(path) for path in paths])


def ending(meta: store.Meta) -> str:
    """How a run came out, in the few words every part of this tool uses for it.

    A timeout has no exit code, so it is named rather than printed as an empty
    one. Said in one place because a run that reads `timed out` at the terminal
    and `exit None` in a listing is two tools wearing one name.
    """
    return "timed out" if meta.timed_out else f"exit {meta.exit_code}"


def state(running: store.Running | None, meta: store.Meta | None) -> str:
    """What to call a run right now, in the one or two words both front ends use.

    `lost` is a word of its own on purpose. A supervisor that is gone without
    having written an ending is not a command that finished: nobody knows how
    that one came out, and printing `exit None` would be claiming otherwise.
    """
    if running is not None:
        return "running" if alive(running) else "lost"
    return ending(meta) if meta is not None else "unknown"


def follow_footer(handle: str, view: View, who: str, first: int, state: str) -> str:
    """Where in a running command this look sits, and whether more is coming.

    The numbers are the ones the whole capture uses, so `sift peek` on any of
    them lands on the line the reader was actually shown. That is the entire
    reason a run is followed by offset rather than by copying each look into a
    capture of its own.
    """
    if not view.total:
        return f"sift {handle} · {state} · nothing new since the last look"
    last = first + view.total - 1
    return (
        f"sift {handle} · {state} · new lines {first:,}-{last:,}"
        f" · {view.kept:,} shown · {who}" + silence(view)
    )


def outline_footer(path: str, view: View, who: str) -> str:
    """The same line for a file: how much of it is here, and who left the rest out."""
    return f"sift {path} · {counted(view)} · {who}" + silence(view)


def counted(view: View) -> str:
    """How much of it is here, in whatever the view was counting.

    The word comes off the view rather than being written into each footer,
    because a footer that says "lines" about a count of records is not a wording
    slip: it is the one number this tool publishes about itself, described as
    something it is not.
    """
    return f"{view.kept:,}/{view.total:,} {view.unit}s"


def silence(view: View) -> str:
    """What to add when part of the capture was never actually looked at.

    A short view and an incomplete view read the same. Both say a small number
    out of a large one, in the same words, with the same confidence. The
    difference is that one of them is a choice and the other is a gap, and only
    this line tells the reader which one they are holding.
    """
    if not view.unanswered:
        return ""
    asked = "question" if view.unanswered == 1 else "questions"
    return f" · {view.unanswered} {asked} unanswered"


def peek_footer(found: Peek) -> str:
    """No model in this one, so it says only where in the whole this piece sits.

    A search says how many lines it matched as well as which it shows. Those are
    different numbers -- context is added around each match and the answer is
    capped -- and a reader who is told only the second cannot tell whether they
    have seen everything their pattern found.
    """
    where = (
        f"sift {found.handle} · lines {found.first_line:,}-{found.last_line:,}"
        f" of {found.total_lines:,}"
    )
    if not found.matched:
        return where
    line = "line" if found.matched == 1 else "lines"
    return f"{where} · {found.matched:,} {line} matched"
