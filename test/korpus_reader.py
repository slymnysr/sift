"""Reading the corpus: what each sample is, and what is expected of it.

Samples are read as bytes and decoded, never with `read_text()`. Reading text
turns on universal newlines, which quietly rewrites a carriage return into a
newline -- and a progress bar that redraws itself would arrive as a hundred
lines that were never in the file. `sift` reads captures as bytes for exactly
that reason, and a corpus that measures `sift` has to be read the same way.

A sample is a pair of files with the same stem in `test/korpus/`:

    <name>.txt    the output of a command, exactly as it was written
    <name>.json   what is known about it

The labels are:

    tool        the program that wrote it, for reporting
    language    the human language in it, as an ISO 639-1 code
    script      latin, cyrillic, arabic, devanagari, cjk, hebrew, ...
    failed      whether the run ended badly
    lines       how many lines it has, so the count can be checked
    must_show   the lines a view is wrong without
    noise       ranges that could all be folded away and cost nothing
    note        why this sample is in the corpus

Lines that are in neither list are context: helpful, not required, not
penalised. Keeping `must_show` small is deliberate. Demanding that an underline
or a `|` be shown would not make the measurement stricter, only wrong.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sift import lines as text_lines
from sift import store
from sift.capture import Capture

KORPUS = Path(__file__).parent / "korpus"


@dataclass(frozen=True)
class Sample:
    name: str
    text: str
    body: list[str]
    tool: str
    language: str
    script: str
    failed: bool
    claimed_lines: int
    must_show: tuple[int, ...]
    noise: frozenset[int]
    note: str

    @property
    def total(self) -> int:
        return len(self.body)

    def line(self, number: int) -> str:
        return self.body[number - 1]


def load(name: str) -> Sample:
    label = json.loads((KORPUS / f"{name}.json").read_bytes().decode("utf-8"))
    text = (KORPUS / f"{name}.txt").read_bytes().decode("utf-8")
    noise: set[int] = set()
    for start, end in label["noise"]:
        noise.update(range(start, end + 1))
    return Sample(
        name=name,
        text=text,
        body=text_lines.of(text),
        tool=label["tool"],
        language=label["language"],
        script=label["script"],
        failed=label["failed"],
        claimed_lines=label["lines"],
        must_show=tuple(label["must_show"]),
        noise=frozenset(noise),
        note=label["note"],
    )


def names() -> list[str]:
    return sorted(p.stem for p in KORPUS.glob("*.json"))


def every() -> list[Sample]:
    return [load(name) for name in names()]


def as_capture(sample: Sample) -> Capture:
    """The sample stored and read back the way a real run would be.

    Not a stand-in for a capture -- the bytes go out through `store.begin` and
    come back through `store.read_raw`, so anything that would go wrong between
    the pipe and the view goes wrong here too.
    """
    data = sample.text.encode("utf-8")
    handle = store.new_handle(["korpus", sample.name], store.now())
    store.begin(handle).write_bytes(data)
    meta = store.Meta(
        handle=handle,
        command=["korpus", sample.name],
        shell=False,
        exit_code=1 if sample.failed else 0,
        timed_out=False,
        started_at=store.now(),
        duration_s=0.0,
        byte_count=len(data),
        cwd=str(KORPUS),
    )
    store.finish(meta)
    return Capture(meta)
