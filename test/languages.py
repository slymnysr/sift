#!/usr/bin/env python3
"""Faz 5 -- does the choice work in every language, or only in English?

Everything else in `test/` runs offline, because everything else can be decided
without asking anyone. This cannot. The claim of the whole project is that
`sift` needs no list of languages because the model already knows them all, and
the only way to find out whether that is true is to ask the model about output
in eighteen of them and count what comes back.

So this is a script, not a test. It needs a key, it needs a network, and it
costs one real request per sample.

    uv run python test/languages.py            # every sample
    uv run python test/languages.py ja ko zh   # only the ones matching
    uv run python test/languages.py arabic     # matches script and tool too

Two numbers per sample. How many of the lines a view is *wrong* without came
back -- that is the claim, and it has to be all of them. And how much of the
noise came along -- that is whether the tool is worth running, and it only has
to be small.

A sample missing a required line is not a failing test. It is a measurement, and
it says the choice is weaker in that language than in English. Which is exactly
what this file exists to find out.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import korpus_reader as k
from sift.distill import distill
from sift.model import Bridge


def measure(sample: k.Sample, bridge: Bridge):
    """Ask the model about one sample and count what it chose."""
    view = distill(k.as_capture(sample), bridge)
    if view is None:
        return None, set()
    shown = set()
    number = 0
    for line in view.text.split("\n"):
        if "not shown · sift peek" in line:
            continue
        number += 1
        shown.add(line)
    return view, shown


def report(sample: k.Sample, view, shown: set[str]) -> tuple[int, int, int]:
    """One row of the table. Returns (required found, required, noise kept)."""
    if view is None:
        print(f"{sample.name:18} {sample.language:4} {sample.script:10} " f"-- no answer --")
        return 0, len(sample.must_show), 0

    missed = [n for n in sample.must_show if sample.line(n) not in shown]
    found = len(sample.must_show) - len(missed)
    noise_kept = sum(1 for n in sample.noise if sample.line(n) in shown)
    part = f"{view.kept}/{view.total}"
    mark = " " if not missed else "<"
    print(
        f"{sample.name:18} {sample.language:4} {sample.script:10} {part:>9} "
        f"{found:>3}/{len(sample.must_show):<3} {noise_kept:>3}/{len(sample.noise):<3} {mark}"
    )
    for n in missed:
        print(f"{'':18} eksik {n}: {sample.line(n)[:88]}")
    return found, len(sample.must_show), noise_kept


def main(argv: list[str] | None = None) -> int:
    words = [w.lower() for w in (argv if argv is not None else sys.argv[1:])]
    samples = [
        s
        for s in k.every()
        if not words
        or any(w in f"{s.name} {s.language} {s.script} {s.tool}".lower() for w in words)
    ]
    if not samples:
        print(f"No sample matches {' '.join(words)!r}.")
        return 2

    home = tempfile.TemporaryDirectory(prefix="sift-korpus-")
    os.environ["SIFT_HOME"] = home.name

    bridge = Bridge()
    print(f"{'sample':18} {'lang':4} {'script':10} {'shown':>9} {'must':>7} {'noise':>7}")
    print("-" * 68)

    found = required = noise_kept = noise_total = kept = total = 0
    used: set[str] = set()
    for sample in samples:
        view, shown = measure(sample, bridge)
        a, b, c = report(sample, view, shown)
        found += a
        required += b
        noise_kept += c
        noise_total += len(sample.noise)
        if view is not None:
            kept += view.kept
            total += view.total
            if view.model:
                used.add(view.model)

    print("-" * 68)
    if not total:
        print(f"No model answered. {bridge.last_error or 'no key'}")
        return 2
    print(
        f"{len(samples)} samples · {found}/{required} required lines shown · "
        f"{noise_kept}/{noise_total} noise lines kept · "
        f"{kept}/{total} of the corpus shown ({kept * 100 // total}%)"
    )
    print(f"model: {', '.join(sorted(used))}")
    if found < required:
        print("A missing required line is a measurement, not a bug. It says the")
        print("choice is weaker in that language than in English.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
