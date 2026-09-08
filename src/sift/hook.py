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

import contextlib
import json
import os
from pathlib import Path

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


# Where the client keeps the settings this would be written into, and the one
# line that would be written. `SIFT_SETTINGS` moves it, which is how this is
# tested without touching the file somebody actually uses.
SETTINGS = "~/.claude/settings.json"
COMMAND = "sift hook"
EVENT = "PreToolUse"
MATCHER = "Bash"

# What somebody is told before they are asked. Everything it gives and
# everything it costs, in the order somebody deciding would want them.
OFFER = """\
sift can also catch the shell commands the client runs on its own.

Right now sift only sees what you or the client explicitly hand it. A coding
agent runs a great deal of shell besides that, and all of it lands in the
conversation whole -- and is re-sent on every turn after.

With this on, every shell command the client runs goes through sift first: it
runs the command, keeps every byte, and hands back the lines that mattered.
Nothing decides which commands are "worth" catching, because how much a command
prints is not knowable before it runs. Twelve lines in, twelve lines out.

What it costs, honestly:

  * A command that outruns the client's hook timeout is killed there, and the
    client then runs it itself -- so a very long command can run twice. Keep
    this in mind for anything that should not happen twice.
  * Every caught command costs one model request.

It fails open: a bug in it leaves your shell exactly as it was, and
`SIFT_HOOK=0` switches it off without touching your settings again.

This would add one line to {where}:

    {event} / {matcher} -> {command}

Nothing already in that file is changed or removed."""


def settings_file() -> Path:
    """The settings file this writes into, with `SIFT_SETTINGS` overriding."""
    return Path(os.environ.get("SIFT_SETTINGS") or SETTINGS).expanduser()


def offer() -> str:
    """The notice, with the real paths filled in."""
    return OFFER.format(
        where=settings_file(), event=EVENT, matcher=MATCHER, command=COMMAND
    )


def _entries(settings: dict) -> list | None:
    """The list this would be added to, or None if the file is not that shape.

    Refusing an unfamiliar shape rather than reshaping it is the whole of the
    safety here. This writes into a file somebody else owns, which may hold
    hooks they depend on; a merge that is not certain what it is merging into
    should not merge.
    """
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return None
    found = hooks.setdefault(EVENT, [])
    return found if isinstance(found, list) else None


def installed(settings: dict | None = None) -> bool:
    """Whether the client is already routing its shell commands here."""
    if settings is None:
        settings = read_settings() or {}
    entries = _entries(dict(settings))
    if entries is None:
        return False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for one in entry.get("hooks", []) or []:
            if isinstance(one, dict) and COMMAND in str(one.get("command", "")):
                return True
    return False


def read_settings() -> dict | None:
    """What is in the settings file, {} if there is none, None if it is not JSON."""
    path = settings_file()
    if not path.is_file():
        return {}
    try:
        found = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return found if isinstance(found, dict) else None


def install() -> tuple[bool, str]:
    """Add the routing, without disturbing anything already there.

    A copy of the original is kept beside it the first time, because this edits
    a file this tool does not own and did not write.
    """
    settings = read_settings()
    if settings is None:
        return False, f"sift: {settings_file()} is not JSON this can add to safely."
    if installed(settings):
        return True, "sift: the shell is already routed here. Nothing to do."

    entries = _entries(settings)
    if entries is None:
        return False, f"sift: {settings_file()} has hooks in a shape this cannot merge."

    path = settings_file()
    backup = path.with_suffix(path.suffix + ".before-sift")
    if path.is_file() and not backup.exists():
        with contextlib.suppress(OSError):
            backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    for entry in entries:
        if isinstance(entry, dict) and entry.get("matcher") == MATCHER:
            mine = entry.setdefault("hooks", [])
            if isinstance(mine, list):
                mine.append({"type": "command", "command": COMMAND})
                break
            return False, f"sift: the {MATCHER} entry has hooks this cannot merge."
    else:
        entries.append(
            {"matcher": MATCHER, "hooks": [{"type": "command", "command": COMMAND}]}
        )

    settings.setdefault("hooks", {})[EVENT] = entries
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        return False, f"sift: could not write {path} ({exc})"

    kept = f" The file as it was is in {backup.name}." if backup.exists() else ""
    return True, (
        f"sift: the shell is routed here now. Restart the client for it to take"
        f" effect.{kept}\n"
        f"      Undo with `sift hook --uninstall`, or switch it off for one"
        f" session with SIFT_HOOK=0."
    )


def uninstall() -> tuple[bool, str]:
    """Take the routing out again, and leave everything else exactly as it was."""
    settings = read_settings()
    if settings is None:
        return False, f"sift: {settings_file()} is not JSON this can edit safely."
    if not installed(settings):
        return True, "sift: the shell was not routed here. Nothing to do."

    entries = _entries(settings) or []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        mine = entry.get("hooks")
        if isinstance(mine, list):
            entry["hooks"] = [
                one
                for one in mine
                if not (isinstance(one, dict) and COMMAND in str(one.get("command", "")))
            ]
    # An entry whose only hook was this one is removed; one that had others keeps
    # them. Leaving an empty matcher behind would be leaving litter in somebody
    # else's file.
    settings["hooks"][EVENT] = [
        entry
        for entry in entries
        if not (isinstance(entry, dict) and entry.get("hooks") == [])
    ]
    try:
        settings_file().write_text(
            json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        return False, f"sift: could not write {settings_file()} ({exc})"
    return True, "sift: the shell is no longer routed here."
