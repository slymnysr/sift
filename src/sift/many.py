"""Several questions at once, and the one number that keeps them honest.

Everything else in this tool answers one question about one thing. This runs
several of those side by side: four log files digested together, three running
commands read in one call, a directory outlined in the time one file used to
take.

The whole module is a dozen lines, because the hard part is not here. Asking in
parallel is easy; asking in parallel *without multiplying the load* is what took
a day to learn, and that lesson lives one layer down. Every ask in this project
passes through `distill.in_flight`, a single gate sized by `SIFT_WORKERS`. So
this file may start as many jobs as it likes and the number of requests actually
in the air is still the number the machine was told to allow.

That division of labour is deliberate. A ceiling that each caller has to work
out for itself is a ceiling that the next caller will get wrong -- and the next
caller is always the one written six months later by someone who never read the
note. The gate cannot be got wrong by arithmetic, because there is none to do.

What this file does own is the promise that **the answers come back in the order
the questions were asked**. Which of them finishes first is a fact about the
network, and a result that reordered itself by network timing would be a
different answer to the same question every time it was asked.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor

from sift.distill import workers


def together[T](jobs: Sequence[Callable[[], T]]) -> list[T]:
    """Run every job at the same time and return what they returned, in order.

    One job is run directly rather than through a pool, because a pool for one
    job is a thread and a queue doing what a call does.

    An exception from a job comes back out of here, at the position that job
    would have had. Swallowing it would leave the caller a list with a hole in
    it and nothing to say what happened -- and every caller above this one
    already has a net of its own that turns a failure into a view.
    """
    if not jobs:
        return []
    if len(jobs) == 1:
        return [jobs[0]()]

    with ThreadPoolExecutor(max_workers=min(workers(), len(jobs))) as pool:
        return list(pool.map(lambda job: job(), jobs))
