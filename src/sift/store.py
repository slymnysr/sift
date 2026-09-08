"""Where a capture lives after the command has finished.

The store is the reason `sift` can promise that nothing is thrown away. Whatever
the command wrote goes to disk first, exactly as it arrived, and every view
built later is a *selection over this file* rather than a replacement for it.
Deciding what matters is a judgement and judgements are wrong sometimes; the
cost of being wrong has to stay at one line of a view, never at a lost byte.

Layout, one directory per capture:

    $SIFT_HOME/captures/<handle>/raw         the bytes, untouched
    $SIFT_HOME/captures/<handle>/meta.json   what was run, how it ended
    $SIFT_HOME/captures/<handle>/running.json a command still going
    $SIFT_HOME/captures/<handle>/read.json    how much of it a reader has seen

`raw` is opened in binary and never rewritten. `meta.json` is written once the
command has finished, which also makes it the marker for a complete capture: a
directory with `raw` but no `meta.json` is a run that was interrupted.

A third file, `view.json`, is written when a view is built: what the capture
cost and what the reader was handed instead. It is what `sift stats` adds up,
and it sits beside the capture rather than in a log of its own so that removing
a capture removes the claim made about it, with nothing left to keep in step.

`running.json` and `read.json` belong to commands that have not finished. The
first says a process was started and left going; the second says how far into
its output a reader has already been taken. Both are files rather than something
held in memory because every `sift` invocation is its own process: a cursor kept
in memory would start over at zero each time, and the reader would be handed the
same thousand lines again -- which is the cost this tool exists to avoid.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

_HANDLE_LENGTH = 8


def home() -> Path:
    """The root under which captures are kept.

    Read from the environment on every call rather than cached at import, so a
    test can point it somewhere temporary without reloading the module.
    """
    if os.environ.get("SIFT_HOME"):
        return Path(os.environ["SIFT_HOME"]).expanduser()
    base = os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")
    return Path(base).expanduser() / "sift"


def captures_dir() -> Path:
    return home() / "captures"


@dataclass(frozen=True)
class Meta:
    """What a capture knows about itself once the command has stopped."""

    handle: str
    command: list[str]
    shell: bool
    exit_code: int | None
    timed_out: bool
    started_at: float
    duration_s: float
    byte_count: int
    cwd: str

    @property
    def failed(self) -> bool:
        """True when the command did not end cleanly.

        A timeout counts as failure even though it has no exit code, because to
        anyone reading the output it is the same event: the thing did not work.
        """
        return self.timed_out or self.exit_code not in (0, None)


def new_handle(command: list[str], started_at: float) -> str:
    """A short, unique name for one run.

    Content-hashing the command would collide the moment the same command is run
    twice, which is the common case, so the clock and the process take part. The
    handle is typed by hand into `sift peek`, so it is kept short.
    """
    import hashlib

    seed = f"{started_at!r}|{os.getpid()}|{' '.join(command)}"
    return hashlib.sha256(seed.encode("utf-8", "replace")).hexdigest()[:_HANDLE_LENGTH]


@dataclass(frozen=True)
class Running:
    """A command that was started and left to run.

    `pid` is the process that was started to look after the command, not the
    command itself. Killing that process's group ends both, and asking whether
    it is alive is asking whether anything is still watching -- which is the
    question a reader actually has.
    """

    handle: str
    command: list[str]
    shell: bool
    cwd: str
    started_at: float
    pid: int


@dataclass(frozen=True)
class Cursor:
    """How far into a capture a reader has already been taken.

    Bytes and lines both, because they answer different questions and neither
    can be worked out from the other without reading the file again: bytes say
    where to start reading, lines say what number the next line has.
    """

    bytes: int = 0
    lines: int = 0


def raw_path(handle: str) -> Path:
    return captures_dir() / handle / "raw"


def meta_path(handle: str) -> Path:
    return captures_dir() / handle / "meta.json"


def running_path(handle: str) -> Path:
    return captures_dir() / handle / "running.json"


def cursor_path(handle: str) -> Path:
    return captures_dir() / handle / "read.json"


def begin(handle: str) -> Path:
    """Make room for a capture and hand back the file to write bytes into."""
    d = captures_dir() / handle
    d.mkdir(parents=True, exist_ok=True)
    return d / "raw"


def finish(meta: Meta) -> None:
    """Record how the run ended. Writing this file is what marks it complete."""
    meta_path(meta.handle).write_text(
        json.dumps(asdict(meta), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def mark_running(started: Running) -> None:
    """Record that a command was started and nobody is waiting for it."""
    running_path(started.handle).write_text(
        json.dumps(asdict(started), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_running(handle: str) -> Running | None:
    """What was started under this handle, or None if nothing was left going.

    A capture that has finished is not running whatever the file says: the
    marker is removed at the end, but a process killed hard enough never gets to
    remove it, and `meta.json` is the older and more trustworthy of the two.
    """
    if meta_path(handle).is_file():
        return None
    p = running_path(handle)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    fields = set(Running.__dataclass_fields__)
    try:
        return Running(**{k: v for k, v in data.items() if k in fields})
    except TypeError:
        return None


def clear_running(handle: str) -> None:
    """Forget the marker, whether or not it was there."""
    with contextlib.suppress(OSError):
        running_path(handle).unlink()


def started() -> list[Running]:
    """Every command left going, newest first."""
    d = captures_dir()
    if not d.is_dir():
        return []
    found = [load_running(p.name) for p in d.iterdir() if p.is_dir()]
    alive = [r for r in found if r is not None]
    alive.sort(key=lambda r: r.started_at, reverse=True)
    return alive


def load_cursor(handle: str) -> Cursor:
    """How much of this capture a reader has already been handed.

    Nothing read is the honest answer for a capture nobody has looked at and for
    one whose cursor cannot be read, so both come back the same: a reader shown
    a line twice has lost nothing but patience, and one shown nothing has lost
    the output.
    """
    p = cursor_path(handle)
    if not p.is_file():
        return Cursor()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return Cursor(bytes=int(data["bytes"]), lines=int(data["lines"]))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return Cursor()


def save_cursor(handle: str, cursor: Cursor) -> None:
    """Move the cursor, and never let moving it cost the caller their output."""
    with contextlib.suppress(OSError):
        cursor_path(handle).write_text(
            json.dumps(asdict(cursor), ensure_ascii=False, indent=2), encoding="utf-8"
        )


def load(handle: str) -> Meta | None:
    """The metadata for a finished capture, or None if there is no such capture.

    An interrupted run -- bytes on disk, no `meta.json` -- reads as absent here,
    while `read_raw` will still hand back what it managed to write. That split is
    deliberate: the bytes are always worth keeping, the claims about them are not
    worth making up.
    """
    p = meta_path(handle)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    fields = {f for f in Meta.__dataclass_fields__}
    return Meta(**{k: v for k, v in data.items() if k in fields})


def read_raw(handle: str) -> bytes:
    """Every byte the command wrote, exactly as it wrote them.

    A handle that was never captured raises rather than reading as empty. The
    two look identical on screen -- nothing -- and they mean opposite things:
    "the command said nothing" against "you are asking about something that is
    not here". Silently answering the first when asked the second sends someone
    looking for a bug in their command.
    """
    p = raw_path(handle)
    if not p.is_file():
        raise FileNotFoundError(f"no capture named {handle!r}")
    return p.read_bytes()


def recent(limit: int = 20) -> list[Meta]:
    """Finished captures, newest first."""
    d = captures_dir()
    if not d.is_dir():
        return []
    metas = [m for m in (load(p.name) for p in d.iterdir() if p.is_dir()) if m is not None]
    metas.sort(key=lambda m: m.started_at, reverse=True)
    return metas[:limit]


@dataclass(frozen=True)
class Saving:
    """What one view cost, next to what it stood for."""

    handle: str
    raw_bytes: int
    shown_bytes: int
    kept: int
    total: int
    model: str | None
    asks: int
    # Defaulted, so that a report written before this field existed still loads
    # as what it was: a run nobody had counted the silent questions of.
    unanswered: int = 0

    @property
    def part(self) -> float:
        """The share of the capture the reader was actually handed, as a percent."""
        return self.shown_bytes * 100 / self.raw_bytes if self.raw_bytes else 0.0


def view_path(handle: str) -> Path:
    return captures_dir() / handle / "view.json"


def record(saving: Saving) -> None:
    """Write down what a view cost, and never let the writing cost anything.

    A full disk, a read-only cache, a directory swept up between the run and the
    view -- none of those are reasons for a caller to lose the output they asked
    for. Of everything this tool does, the bookkeeping is the part that may fail
    silently, because it is the only part nobody asked for.
    """
    with contextlib.suppress(OSError):
        view_path(saving.handle).write_text(
            json.dumps(asdict(saving), ensure_ascii=False, indent=2), encoding="utf-8"
        )


def load_saving(handle: str) -> Saving | None:
    """What a view of this capture cost, or None if no view was ever built."""
    p = view_path(handle)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    fields = {f for f in Saving.__dataclass_fields__}
    return Saving(**{k: v for k, v in data.items() if k in fields})


def savings(limit: int = 20) -> list[tuple[Meta, Saving]]:
    """Of the last `limit` runs, those that produced a view, newest first.

    Runs without one are left out rather than counted as saving nothing: a
    capture whose view was never built has not been measured, and a report that
    quietly averaged it in would understate the tool by exactly the number of
    times somebody ran `sift list`.
    """
    pairs = []
    for meta in recent(limit):
        found = load_saving(meta.handle)
        if found is not None:
            pairs.append((meta, found))
    return pairs


def now() -> float:
    return time.time()
