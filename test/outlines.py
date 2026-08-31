#!/usr/bin/env python3
"""Faz 6 -- can a model outline a language nobody wrote a rule for?

`test/languages.py` asks whether the choice survives the human language. This
asks whether it survives the programming language, and it is the measurement the
whole phase turns on: the design being replaced held a thousand lines of regular
expressions, one entry per language, and the question is whether deleting all of
it cost anything.

Every sample sits under a `.txt` name. Nothing that reads a suffix can score
here, so whatever score comes back was earned by reading the file.

    uv run python test/outlines.py             # every sample
    uv run python test/outlines.py haskell     # only the ones matching
    uv run python test/outlines.py invented    # matches the syntax family too

Two numbers per sample, as in Faz 5, but they mean something different here. The
declarations are the lines an outline is *wrong* without -- a table of contents
that skips a function has misled the reader about what the file contains. The
bodies are the statements inside those functions; keeping a few is untidy, and
keeping most of them means the outline has become the file again.

A missing declaration is not a failing test. It is the number that says what
the table would have bought, if it had been kept.
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import korpus_reader as k
from sift.model import Bridge
from sift.outline import outline


def measure(sample: k.Sample, bridge: Bridge):
    """Outline one sample and collect the lines it showed."""
    view = outline(k.path_of(sample), bridge)
    if view is None:
        return None, set()
    shown = {
        line for line in view.text.split("\n") if "not shown · sift peek" not in line
    }
    return view, shown


def who(view) -> str:
    """The model's name without the vendor in front of it.

    Worth a column of its own: the bridge falls back to a smaller model when the
    first one is busy, and a row that collapsed is a different finding depending
    on which of them was answering.
    """
    return (view.model or "-").rsplit("/", 1)[-1][:18]


def report(sample: k.Sample, view, shown: set[str]) -> tuple[int, int, int]:
    """One row of the table. Returns (declarations found, declarations, bodies kept)."""
    head = f"{sample.name:20} {sample.family:12}"
    if view is None:
        print(f"{head} -- no answer --")
        return 0, len(sample.must_show), 0

    missed = [n for n in sample.must_show if sample.line(n) not in shown]
    found = len(sample.must_show) - len(missed)
    bodies_kept = sum(1 for n in sample.noise if sample.line(n) in shown)
    part = f"{view.kept}/{view.total}"
    mark = " " if not missed else "<"
    print(
        f"{head} {who(view):18} {part:>8} {found:>3}/{len(sample.must_show):<3} "
        f"{bodies_kept:>3}/{len(sample.noise):<3} {mark}"
    )
    for n in missed:
        print(f"{'':20} eksik {n}: {sample.line(n).strip()[:80]}")
    return found, len(sample.must_show), bodies_kept


def by_family(rows: list[tuple[k.Sample, int, int, int]]) -> None:
    """The breakdown that answers the question the table could not.

    A brace-shaped regular expression does well on braces. Whether anything was
    lost by throwing it away shows up in the families it never handled: `end`
    keywords, bare equations, Make rules, Lisp forms, and a language invented
    for this corpus that no rule anywhere has ever seen.
    """
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for sample, found, required, bodies in rows:
        row = totals[sample.family]
        row[0] += found
        row[1] += required
        row[2] += bodies
        row[3] += len(sample.noise)
    print()
    print(f"{'family':14} {'declarations':>14} {'bodies kept':>14}")
    for family in sorted(totals):
        found, required, bodies, noise = totals[family]
        print(f"{family:14} {found:>7}/{required:<6} {bodies:>7}/{noise:<6}")


def main(argv: list[str] | None = None) -> int:
    words = [w.lower() for w in (argv if argv is not None else sys.argv[1:])]
    samples = [
        s
        for s in k.every(k.KAYNAK)
        if not words or any(w in f"{s.name} {s.language} {s.family}".lower() for w in words)
    ]
    if not samples:
        print(f"No sample matches {' '.join(words)!r}.")
        return 2

    home = tempfile.TemporaryDirectory(prefix="sift-kaynak-")
    os.environ["SIFT_HOME"] = home.name

    bridge = Bridge()
    print(f"{'sample':20} {'family':12} {'model':18} {'shown':>8} {'decl':>7} {'body':>7}")
    print("-" * 80)

    rows: list[tuple[k.Sample, int, int, int]] = []
    found = required = bodies_kept = bodies_total = kept = total = 0
    used: set[str] = set()
    for sample in samples:
        view, shown = measure(sample, bridge)
        a, b, c = report(sample, view, shown)
        rows.append((sample, a, b, c))
        found += a
        required += b
        bodies_kept += c
        bodies_total += len(sample.noise)
        if view is not None:
            kept += view.kept
            total += view.total
            if view.model:
                used.add(view.model)

    print("-" * 80)
    if not total:
        print(f"No model answered. {bridge.last_error or 'no key'}")
        return 2
    print(
        f"{len(samples)} samples · {found}/{required} declarations shown · "
        f"{bodies_kept}/{bodies_total} bodies kept · "
        f"{kept}/{total} of the corpus shown ({kept * 100 // total}%)"
    )
    print(f"model: {', '.join(sorted(used))}")
    by_family(rows)
    if found < required:
        print()
        print("A missing declaration is a measurement, not a bug. It is the size of")
        print("what the thousand-line table would have bought, had it been kept.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
