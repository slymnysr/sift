#!/usr/bin/env python3
"""Faz 8 -- what a ceiling costs, measured instead of assumed.

Faz 7 measured the finished tool on a real command and found it handing back a
third of a 10,000-line lint run. The cause was arithmetic, not judgement: a
capture too long for one ask is split, every piece was told to keep a hundred
lines, and the pieces were added together. Faz 8 divides the budget between the
pieces and hands an over-long answer back rather than cutting it.

Dividing is free to write and is not free to use. A model asked for twenty lines
instead of a hundred and twenty will leave something out, and the only question
worth asking is *what*. So this script asks the corpus, at four budgets: how
many of the lines a reader could not do without still come back, and how much
noise comes with them.

    uv run python test/budget.py            # every budget
    uv run python test/budget.py 20 120     # only these
    SIFT_WORKERS=1 uv run python test/budget.py     # one at a time

Samples are asked about in parallel, because they have nothing to do with each
other: one sample's ceiling cannot change another's answer, and the process
spends its whole life waiting on a socket. Measured on this corpus the run was
network-bound end to end -- twenty-three minutes of wall clock against zero
seconds of CPU.

Parallelism is not free of consequence here, and the consequence is not speed.
Enough requests at once and the endpoint starts refusing them; `Bridge` answers
a refusal by trying once more and then dropping to a lower rung of the ladder.
That is the right behaviour for the tool -- a smaller answer beats no answer --
and the wrong behaviour for a measurement: rows answered by different models
compare models, not budgets. It is not a hypothetical. The first parallel run of
this script came back with every row split between the 550b and the 120b, and a
tighter budget appearing to find *more* required lines than a looser one.

So the ladder is pinned to a single rung here. A refused request is then retried
once and, if it is refused again, comes back as no answer at all -- which lands
in `missed` where a reader will see it, instead of quietly becoming a smaller
model's opinion. Pinning is what makes the comparison controlled; `SIFT_MODELS`
overrides it, and `report` still names the models per row so that an override
with more than one rung cannot pass unnoticed.

Like `languages.py` and `outlines.py` this is a script and not a test: it needs
a key, it needs the network, and it costs one real request per sample per
budget. A required line lost at a tight budget is not a failure. It is the
price, and printing it is how the default gets chosen by measurement rather than
by whichever number looked reasonable while the code was being written.

The one thing here that *is* a failure is a required line lost at the default
budget, because that is the setting everybody who never reads this file will
get. That, and only that, comes back as a non-zero exit code.
"""

from __future__ import annotations

import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import korpus_reader as k
from sift import lines as text_lines
from sift.distill import BUDGET, QUESTION, select
from sift.model import Bridge, default_ladder, find_key

# Tight, half, the default, and no ceiling at all. The last one is the tool as
# Faz 7 left it, kept in the table so the cost of the fix is visible next to it
# rather than described.
BUDGETS: tuple[int | None, ...] = (20, 60, BUDGET, None)

# How many samples are in flight at once, and -- once `main` has had its say --
# how many requests are in flight at once, full stop. Low enough that a free
# endpoint does not start refusing, high enough that the run is not a queue of
# one.
WORKERS = max(1, int(os.environ.get("SIFT_WORKERS", "6")))


@dataclass
class Row:
    """One budget's answer, added up over the whole corpus."""

    budget: int | None
    counted: int = 0
    found: int = 0
    required: int = 0
    noise_kept: int = 0
    noise_total: int = 0
    kept: int = 0
    total: int = 0
    asks: int = 0
    missed: list[str] = field(default_factory=list)
    silent: list[str] = field(default_factory=list)
    models: set[str] = field(default_factory=set)

    @property
    def name(self) -> str:
        return "none" if self.budget is None else str(self.budget)


def measure(sample: k.Sample, budget: int | None):
    """One sample, distilled under one ceiling.

    The bridge is built here rather than shared, so that threads have nothing
    between them: everything a `Bridge` holds after construction is read-only
    except `last_error`, and two samples failing at once must not overwrite each
    other's account of why.
    """
    capture = k.as_capture(sample)
    return select(
        text_lines.of(capture.text()), QUESTION, capture.handle, Bridge(), budget=budget
    )


def score(samples: list[k.Sample], budget: int | None, workers: int = WORKERS) -> Row:
    """One budget, over the whole corpus.

    The asking is done in parallel and the adding up is not: `map` hands results
    back in the order it was given them, so the row is the same row a serial run
    would have produced, and `missed` reads in corpus order rather than in
    whichever order the network happened to answer.
    """
    row = Row(budget)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        views = list(pool.map(lambda sample: measure(sample, budget), samples))
    for sample, view in zip(samples, views, strict=True):
        _fold(row, sample, view)
    return row


def _fold(row: Row, sample: k.Sample, view) -> None:
    """Add one sample's answer to the row it belongs to.

    A sample the endpoint refused is not a sample the budget lost. It is kept
    out of the row's arithmetic and counted on its own line, for exactly the
    reason `View.unanswered` exists in the tool: a view that left a line out and
    a view that never saw it read the same, and only one of them is a decision
    about the ceiling.

    This is not hypothetical either. The first pinned run of this script put
    five refusals into one budget's column and none into another's, and the
    table then said the default budget loses a third of the required lines --
    a statement about a free endpoint's mood, printed as a statement about
    arithmetic.
    """
    if view is None or view.unanswered:
        why = (
            "no answer at all"
            if view is None
            else f"{view.unanswered}/{view.asks} unanswered"
        )
        row.silent.append(f"{sample.name}: {why}")
        return

    row.counted += 1
    row.required += len(sample.must_show)
    row.noise_total += len(sample.noise)

    shown = {
        line for line in view.text.split("\n") if "not shown · sift peek" not in line
    }
    for number in sample.must_show:
        if sample.line(number) in shown:
            row.found += 1
        else:
            row.missed.append(f"{sample.name} {number}: {sample.line(number)[:70]}")
    row.noise_kept += sum(1 for n in sample.noise if sample.line(n) in shown)
    row.kept += view.kept
    row.total += view.total
    row.asks += view.asks
    if view.model:
        row.models.add(view.model)


def report(rows: list[Row]) -> None:
    print(
        f"{'budget':>6}  {'required':>10}  {'noise':>10}  {'shown':>13}"
        f"  {'asks':>5}  {'over':>5}  {'silent':>6}"
    )
    print("-" * 70)
    for row in rows:
        shown = f"{row.kept:,}/{row.total:,}"
        part = f"{row.kept * 100 / row.total:.0f}%" if row.total else "--"
        print(
            f"{row.name:>6}  {row.found:>4}/{row.required:<5}"
            f"  {row.noise_kept:>4}/{row.noise_total:<5}  {shown:>8} {part:>4}"
            f"  {row.asks:>5}  {row.counted:>5}  {len(row.silent):>6}"
        )
    print("-" * 70)
    if len({row.counted for row in rows}) > 1:
        print(
            "\nThe rows are over different numbers of samples, because the "
            "endpoint\nanswered for different ones. Compare them knowing that."
        )
    for row in rows:
        if len(row.models) > 1:
            print(
                f"\nbudget {row.name} was answered by more than one model: "
                f"{', '.join(sorted(row.models))}."
            )
            print(
                "  Rows answered by different models are not comparable. "
                "Rerun with SIFT_WORKERS=1."
            )
    for row in rows:
        if row.missed:
            print(f"\nbudget {row.name} left out:")
            for line in row.missed:
                print(f"  {line}")
    for row in rows:
        if row.silent:
            print(f"\nbudget {row.name} never got an answer for:")
            for line in row.silent:
                print(f"  {line}")


def verdict(rows: list[Row]) -> tuple[list[str], list[str]]:
    """What the default ceiling cost, told apart from what it did not cause.

    A required line the corpus loses at every setting -- including with no
    ceiling at all -- was not lost to the ceiling. Charging it to the ceiling
    reports a judgement the model made as a defect in arithmetic, which is the
    same error as reporting a refused request as a budget losing lines. Both
    make the measurement say something true about the run and false about the
    tool.

    Comes back as the lines the ceiling cost and the lines that went missing
    with or without it. With no unbounded row in the run there is nothing to
    compare against, and then every miss is charged to the ceiling: an unproven
    accusation is the safer of the two mistakes here.
    """
    default = next((row for row in rows if row.budget == BUDGET), None)
    if default is None:
        return [], []
    loose = next((row for row in rows if row.budget is None), None)
    if loose is None:
        return list(default.missed), []
    without = set(loose.missed)
    cost = [line for line in default.missed if line not in without]
    anyway = [line for line in default.missed if line in without]
    return cost, anyway


def main(argv: list[str] | None = None) -> int:
    words = list(argv if argv is not None else sys.argv[1:])
    budgets = [
        b
        for b in BUDGETS
        if not words or str(b) in words or (b is None and "none" in words)
    ]
    if not budgets:
        print(f"No budget matches {' '.join(words)!r}. Try: 20 60 {BUDGET} none")
        return 2
    if find_key() is None:
        print("No key, so nothing would be measured but the fallback. Set SIFT_API_KEY.")
        return 2

    home = tempfile.TemporaryDirectory(prefix="sift-budget-")
    os.environ["SIFT_HOME"] = home.name
    # One rung, so that what differs between rows is the budget and nothing else.
    os.environ.setdefault("SIFT_MODELS", default_ladder()[0])
    # `SIFT_WORKERS` is read twice: here, for samples in flight, and again inside
    # `select`, for the pieces of one sample. Left alone the two multiply, and six
    # became thirty-six requests at once -- which is how the first pinned run
    # collected five refusals and reported them as a budget losing lines. The
    # inner pass is pinned to one so that the number above is the whole of it.
    os.environ["SIFT_WORKERS"] = "1"

    samples = k.every()
    rows = [score(samples, budget) for budget in budgets]
    report(rows)

    print(
        f"\n{len(samples)} samples of command output, each distilled at "
        f"{len(budgets)} budgets, {WORKERS} at a time, "
        f"by {os.environ['SIFT_MODELS']}."
    )
    print(
        "A tighter budget that keeps every required line is a smaller view of "
        "the same\nanswer. One that loses a required line has been told to say "
        "less than the\ncommand had to say, and the number above is what that costs."
    )

    # Only over the samples the default budget was actually answered for. A row
    # that lost lines to a refusal has not been measured, and failing on it would
    # be reporting the endpoint's load as a defect in the tool.
    cost, anyway = verdict(rows)
    if anyway:
        print("\nMissing with the ceiling and without it, so not the ceiling's doing:")
        for line in anyway:
            print(f"  {line}")
    if cost:
        print(
            f"\nThe default budget ({BUDGET}) lost a required line that no ceiling "
            f"kept. That is a bug."
        )
        for line in cost:
            print(f"  {line}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
