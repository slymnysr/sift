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

from sift import store
from sift.capture import Capture
from sift.distill import View, distill
from sift.fallback import fallback
from sift.model import Bridge
from sift.outline import ends_of, outline
from sift.peek import Peek


def best_view(capture: Capture) -> tuple[View, str]:
    """The best view of a capture, a word about where it came from, and the bill.

    A view built without a model is recorded too. It cost the caller whatever it
    cost them, and a report that counted only the good runs would be measuring
    the tool on its best days.
    """
    view, who = _choose(capture)
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


def _choose(capture: Capture) -> tuple[View, str]:
    """Every failure below lands in the same place: the ends of the capture,
    shown without a model. That is the whole safety net."""
    bridge = Bridge()
    reason = "no model"
    try:
        chosen = distill(capture, bridge)
        if chosen is not None:
            return chosen, chosen.model or "model"
        reason = bridge.last_error or "no lines chosen"
    except Exception as exc:  # a bug here must not cost the caller their output
        reason = f"{type(exc).__name__}: {exc}"
    return fallback(capture), f"no model ({reason})"


def best_outline(path: str) -> tuple[View, str]:
    """The best outline of a file, and a word about where it came from.

    Shaped like `best_view` and for the same reason. The one failure allowed
    through is the file being unreadable, because then there is nothing to show
    and saying so is the only honest answer.
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
    except Exception as exc:  # a bug here must not cost the caller their outline
        reason = f"{type(exc).__name__}: {exc}"
    return ends_of(path), f"no model ({reason})"


def footer(capture: Capture, view: View, who: str) -> str:
    """One line telling the reader what they are looking at, and what they are not."""
    meta = capture.meta
    ending = "timed out" if meta.timed_out else f"exit {meta.exit_code}"
    return (
        f"sift {capture.handle} · {ending} · {view.kept:,}/{view.total:,} lines"
        f" · {who} · {meta.duration_s:.1f}s" + silence(view)
    )


def outline_footer(path: str, view: View, who: str) -> str:
    """The same line for a file: how much of it is here, and who left the rest out."""
    return f"sift {path} · {view.kept:,}/{view.total:,} lines · {who}" + silence(view)


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
    """No model in this one, so it says only where in the whole this piece sits."""
    return (
        f"sift {found.handle} · lines {found.first_line:,}-{found.last_line:,}"
        f" of {found.total_lines:,}"
    )
