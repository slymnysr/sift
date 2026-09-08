"""What this machine already knows about the commands run on it.

Every other module here asks a model something. This one asks nothing, and that
is the design rather than an omission.

The question is *how often was this run here, how did it go, and which failures
keep coming back* -- and every part of that is counting. A model asked to count
would be slower, cost a request, and be wrong sometimes; there is no judgement
in the question for it to supply. Reaching for it anyway would be the same
mistake as a rules engine deciding which lines matter: using the wrong tool
because it is the one the project is proud of.

So the rule this file stands on is the mirror of the rest of the project: **the
model decides what cannot be computed, and nothing else.**

What it can answer is bounded by what is still on disk. A capture that was swept
up took its record with it, because the record lives beside the bytes rather
than in a ledger of its own -- which is what makes deleting a capture actually
delete it. This module says how far back it can see rather than implying it
remembers everything.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sift import store


@dataclass(frozen=True)
class Habit:
    """One command, and everything this machine has seen of it."""

    command: str
    runs: int
    failures: int
    last_ending: str
    last_at: float
    cwds: tuple[str, ...]

    @property
    def never_worked(self) -> bool:
        """True when every run of this command here has failed.

        Worth its own name because it is the one shape that answers a question
        somebody actually asks: *is this thing broken, or is it me?* A command
        that has failed four times out of four in this directory is not a flaky
        test.
        """
        return self.runs > 0 and self.failures == self.runs


def habits(term: str | None = None, cwd: str | None = None, limit: int = 200) -> list[Habit]:
    """What has been run here, most recent first.

    `term` narrows to commands containing it, `cwd` to a directory. Both are
    plain text rather than patterns: this is a memory, not a search engine, and
    somebody typing `pytest` should not have to think about what the letters
    mean to a regular expression.
    """
    seen: dict[str, list[store.Meta]] = {}
    for meta in store.recent(limit):
        written = " ".join(meta.command)
        if term and term not in written:
            continue
        if cwd and meta.cwd != cwd:
            continue
        seen.setdefault(written, []).append(meta)

    found = [_habit(written, runs) for written, runs in seen.items()]
    found.sort(key=lambda one: one.last_at, reverse=True)
    return found


def _habit(written: str, runs: Sequence[store.Meta]) -> Habit:
    newest = max(runs, key=lambda meta: meta.started_at)
    return Habit(
        command=written,
        runs=len(runs),
        failures=sum(1 for meta in runs if meta.failed),
        last_ending="timed out" if newest.timed_out else f"exit {newest.exit_code}",
        last_at=newest.started_at,
        cwds=tuple(sorted({meta.cwd for meta in runs})),
    )


def reach(limit: int = 200) -> int:
    """How many runs are still on disk to remember at all.

    Printed with the answer, because "this has never failed here" means one thing
    after four hundred runs and nothing at all after two.
    """
    return len(store.recent(limit))
