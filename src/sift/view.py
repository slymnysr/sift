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
"""

from __future__ import annotations

from sift.capture import Capture
from sift.distill import View, distill
from sift.fallback import fallback
from sift.model import Bridge
from sift.outline import ends_of, outline
from sift.peek import Peek


def best_view(capture: Capture) -> tuple[View, str]:
    """The best view of a capture, and a word about where it came from.

    Every failure below lands in the same place: the ends of the capture, shown
    without a model. That is the whole safety net.
    """
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
        f" · {who} · {meta.duration_s:.1f}s"
    )


def outline_footer(path: str, view: View, who: str) -> str:
    """The same line for a file: how much of it is here, and who left the rest out."""
    return f"sift {path} · {view.kept:,}/{view.total:,} lines · {who}"


def peek_footer(found: Peek) -> str:
    """No model in this one, so it says only where in the whole this piece sits."""
    return (
        f"sift {found.handle} · lines {found.first_line:,}-{found.last_line:,}"
        f" of {found.total_lines:,}"
    )
