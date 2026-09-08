"""Catching the shell commands a client runs on its own.

The MCP server can only distil what it was asked to distil. Everything else a
client does with a shell -- and a coding agent does a great deal -- lands in the
conversation whole. This closes that gap without a proxy: the client is asked to
send its shell commands here first, `sift` runs them, and what comes back is a
view.

Two decisions, and the first is the one worth arguing about.

**Everything is routed. Nothing decides whether a command "looks noisy".**

That rule was tempting and it is exactly the mistake this project was rewritten
to avoid. A list of commands worth intercepting is a list of tools wearing a
disguise: it would know `pytest` and `cargo` and `npm`, be wrong about the
in-house script, and be confidently silent about the one that printed forty
thousand lines. And it cannot be right in principle -- how much a command prints
is not knowable before it runs.

Routing everything costs nothing, because a view of a short output *is* that
output: the budget only takes hold when there is more than the budget. Twelve
lines in, twelve lines out.

**It fails open, and that is the third rule again.** A bug here, an unreadable
event, a command that could not be started -- every one of them ends with the
client running the command itself, exactly as it would have. A gate that breaks
a shell is worse than no gate, and this one is allowed to break.

`SIFT_HOOK=0` turns it off for someone who wants their shell back untouched.
"""

from __future__ import annotations

import os

from sift.capture import run
from sift.view import best_view, footer

# What this returns when it has nothing to say. An empty answer means "carry on
# as you were", which is the only safe thing to say when something went wrong.
PASS = {}


def wanted() -> bool:
    """Whether shell commands should be routed here at all."""
    return (os.environ.get("SIFT_HOOK") or "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
        "",
    }


def answer(event: dict) -> dict:
    """What to tell the client about one shell command it is about to run.

    The event is whatever the client put on stdin, and it is treated as data
    from somewhere else: every field is checked before it is used, and anything
    unexpected means *carry on*, never an error. A hook that raises on a shape
    it did not expect takes the shell down with it.
    """
    if not wanted():
        return PASS
    if not isinstance(event, dict):
        return PASS
    if event.get("tool_name") != "Bash":
        return PASS

    given = event.get("tool_input")
    command = given.get("command") if isinstance(given, dict) else None
    if not isinstance(command, str) or not command.strip():
        return PASS

    try:
        capture = run([command], shell=True)
        view, who = best_view(capture)
    except Exception:  # a bug here must not cost the caller their shell
        return PASS

    said = view.text + "\n\n" + footer(capture, view, who) if view.text else footer(
        capture, view, who
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": said,
        }
    }
