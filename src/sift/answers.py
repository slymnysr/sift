"""The same question, asked twice.

An agent re-runs a failing test. Somebody digests the same CI log on Monday and
again on Tuesday. A tool result is dropped from a conversation and fetched
again. In each of those the text is byte for byte what it was, the question is
the same question, and the answer is bought a second time.

Two things are paid for it, and the second is the one that took a while to see.
The obvious cost is a request: an ask that has already been answered. The
quieter cost is that the reply may differ. A model asked the same question twice
is allowed to name a slightly different set of lines, so the tool hands back a
slightly different string -- and a client that had cached the first one now has
two, and re-sends the pair on every turn after. A tool whose whole purpose is to
keep a transcript small should not be a source of new strings for it.

**What is kept is the answer, not the view.** The numbers, and what named them.
Never the rendered text -- that has the handle written into every gap marker
(`sift peek 9f2c41ab`), so a view remembered from one capture would send a
reader of another to somebody else's bytes. The numbers are the model's actual
answer; everything downstream of them is arithmetic and is done again, against
the text in hand, for the handle in hand.

So a hit costs a file read and re-renders locally, and nothing that was true of
a fresh view stops being true of a remembered one: the text still comes from the
caller's own bytes, and the gap still names the caller's own capture.

The key is the whole of the input -- the text, the question, the ceiling, where
the numbering starts, and the caller's `keep`. Anything that would change the
answer is in it, so there is no invalidation to get wrong: a changed file is a
different key, and the old entry is simply never asked for again. `sift gc`
sweeps what nothing asks for.

`SIFT_CACHE=0` turns it off, for the one case this cannot serve: measuring the
model itself, where asking twice is the point.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from sift import store

# How much of the digest is kept. Long enough that two different inputs will not
# collide before the sun goes out, short enough to read in a directory listing.
_KEY_LENGTH = 32


def wanted() -> bool:
    """Whether an answer already given may be used again."""
    return (os.environ.get("SIFT_CACHE") or "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def key(text: str, question: str, budget: int | None, first: int) -> str:
    """A name for one question about one text.

    Everything that can change the answer is in here, and nothing that cannot:
    `keep` is absent because it decides what a caller is shown rather than what
    a model said. The parts are joined with a byte that cannot occur in any of
    them, so that two different inputs cannot be run together into one key by
    moving a boundary.
    """
    seed = "\x00".join([text, question, repr(budget), repr(first)])
    return hashlib.sha256(seed.encode("utf-8", "replace")).hexdigest()[:_KEY_LENGTH]


def kept_dir() -> Path:
    return store.home() / "answers"


def where(named: str) -> Path:
    return kept_dir() / f"{named}.json"


@dataclass(frozen=True)
class Answered:
    """What a model said about a text, in the only form it ever says it."""

    chosen: set[int]
    model: str | None
    unanswered: int


def load(named: str) -> Answered | None:
    """The answer given to this question before, or None if it was never asked.

    Anything unreadable reads as never asked. A cache that raised would be a
    cache that can break a run, and nothing here is worth that: the answer it
    holds can always be bought again.
    """
    try:
        data = json.loads(where(named).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        chosen = {
            number
            for start, end in data["chosen"]
            for number in range(int(start), int(end) + 1)
        }
    except (KeyError, TypeError, ValueError):
        return None
    if not chosen:
        return None
    # Touched on the way past, so that `forget` sweeps by when an answer was
    # last wanted rather than by when it was written. An answer about a log
    # somebody reads every morning is not old.
    with contextlib.suppress(OSError):
        os.utime(where(named))
    model = data.get("model")
    return Answered(
        chosen=chosen,
        model=model if isinstance(model, str) else None,
        unanswered=int(data.get("unanswered", 0)),
    )


def save(named: str, chosen: set[int], model: str | None, unanswered: int) -> None:
    """Write down what was chosen, as the ranges a reply is written in.

    Ranges rather than every number, because that is the shape the answer
    arrived in and a hundred and twenty lines of a build are usually four of
    them. Failing to write costs nothing but the next ask.
    """
    if not chosen:
        return
    runs: list[list[int]] = []
    for number in sorted(chosen):
        if runs and number == runs[-1][1] + 1:
            runs[-1][1] = number
        else:
            runs.append([number, number])
    with contextlib.suppress(OSError):
        kept_dir().mkdir(parents=True, exist_ok=True)
        where(named).write_text(
            json.dumps({"chosen": runs, "model": model, "unanswered": unanswered}),
            encoding="utf-8",
        )


def forget(older_than: float, now_at: float | None = None) -> tuple[int, int]:
    """Drop answers nothing has asked for lately. Returns how many, and how big.

    Swept by when they were last *used* rather than when they were written: an
    answer about a log that is read every morning is not old, however long ago
    the log was written. `load` touches the file it reads, which is what makes
    that true.
    """
    where_they_are = kept_dir()
    if not where_they_are.is_dir():
        return (0, 0)
    cut = (store.now() if now_at is None else now_at) - older_than
    count = freed = 0
    for found in sorted(where_they_are.iterdir()):
        if found.suffix != ".json":
            continue
        try:
            stat = found.stat()
            if stat.st_mtime > cut:
                continue
            found.unlink()
        except OSError:
            continue
        count += 1
        freed += stat.st_size
    return (count, freed)
