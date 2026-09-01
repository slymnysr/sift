"""Choosing which lines to show, without ever writing one.

This is the idea the whole tool rests on. The capture is numbered and handed to
a model with a single question -- *which numbers matter?* -- and the model
answers with numbers. Whatever else it says is thrown away without being read.
The view is then printed from the file on disk, line by line, byte for byte.

That is why `sift` is not a summariser and cannot be compared to one. A
summariser writes a sentence about your output and can be wrong about what your
output said. Nothing here writes a line. Being wrong is still possible -- the
wrong lines can be chosen -- but the cost of that mistake is a line missing from
a view, never a line that says something the command never said. And a missing
line is one `sift peek` away, because the file was never touched.

It is also why coverage is not a list. Nothing in this file knows what a stack
trace looks like in Rust, or what a Japanese error message says, or how a
language released last week reports a failure. The model knows all of that
already. There is no table here to be missing an entry.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from sift import lines as text_lines
from sift.capture import Capture
from sift.model import Answer, Bridge

# Every question asked through `select` is answered the same way, because one
# parser reads every answer. `select` appends it rather than each question ending
# with it, so a second question cannot quietly arrive with a second format for
# the reply -- and so it stays last in the prompt, after whatever the question
# and the budget had to say.
ANSWER_FORMAT = (
    "\n"
    "Answer with line numbers only: single numbers or ranges, separated by commas.\n"
    "For example: 1, 40-47, 512\n"
    "Write nothing else. Do not explain, do not quote any line, do not repeat the "
    "text. Only numbers."
)

QUESTION = (
    "You are given the numbered output of a command someone just ran.\n"
    "Choose the lines a person debugging this would need to see: what failed, "
    "what warned, what changed, the final result, and the few lines around them "
    "that make those readable.\n"
    "Leave out repetition, progress that only says work happened, and lines that "
    "carry no information on their own.\n"
)

# One ask covers this much of the transcript. Most captures fit in a single one;
# a long build is split and the answers are added together.
CHARS_PER_ASK = 120_000

# What the second pass adds to whatever question was asked the first time.
#
# Measured, and the measurement is the reason this exists. Handing a shortlist
# back with the original question produced four asks and 359 lines against a
# budget of 120: asked "which lines matter" about a list of lines that all
# matter, a model answers "all of them", and it is right. The second pass is not
# the first pass asked again. It has to say that the list is already the answer
# and is still too long, which is a different question and gets a different
# reply.
NARROWING = (
    "\nThese lines are already an answer to that question, chosen out of a much "
    "longer text, and there are still too many of them to show at once.\n"
    "Choose which of them to keep: prefer a line that carries something none of "
    "the others do over one more example of something already covered.\n"
)

# What a whole view may cost, in lines, however long the capture behind it was.
#
# The number matters less than the fact that there is one. Without it a view is
# a fraction of its capture rather than a size: measured, a 378-line test run
# came back as 5 lines, and the same tool on a 9,984-line lint run came back as
# 2,842 -- no rule broken, every line real, and 181 KB of context spent. A tool
# whose cost grows with the mess it is pointed at is least useful exactly when it
# is needed most.
# How many pieces of one capture are asked about at once.
#
# Measured: `ruff check --select ALL` over this repository is 633,877 bytes,
# which is seven questions of 120,000 characters each, and asking them one after
# another took ten minutes of waiting on a socket with the CPU idle. The pieces
# are disjoint and their answers are unioned, so asking them together changes
# how long the caller waits and nothing else.
WORKERS = 6


def workers() -> int:
    """How many pieces to ask about at once, with `SIFT_WORKERS` overriding."""
    written = os.environ.get("SIFT_WORKERS", "").strip()
    return max(1, int(written)) if written.isdigit() else WORKERS


BUDGET = 120

# How many times an over-long answer may be handed back before its length is
# accepted. Each round costs asks, and a model that has not narrowed after three
# is not going to; the view then comes back long and says how long, which is
# worth more than a shorter view nobody can trust.
NARROW_ROUNDS = 3

# Only in the prompt. A line thousands of characters wide is nearly always
# machine noise, and the model needs its beginning to judge it, not all of it.
# What gets shown is never shortened -- that comes from the file.
PROMPT_LINE_CAP = 400

# Ranges written the way a model writes them: a hyphen, or one of the dashes a
# text generator reaches for instead (U+2013, U+2014). Escaped rather than typed
# so that a dash nobody can see in a diff cannot go missing from here.
_NUMBERS = re.compile(r"(\d+)\s*[-\u2013\u2014]\s*(\d+)|(\d+)")


@dataclass(frozen=True)
class View:
    """A capture with most of it folded away, and a note of what was folded."""

    handle: str
    text: str
    kept: int
    total: int
    model: str | None
    asks: int
    # Questions that came back with nothing. Lines they would have kept are not
    # kept by anything else, so a view missing six answers out of seven reads
    # exactly like a view that got all seven -- shorter, and no less confident.
    # Counting them is what lets the footer tell those two apart.
    unanswered: int = 0

    @property
    def folded(self) -> int:
        return self.total - self.kept


def rows(pairs: Iterable[tuple[int, str]], cap: int = PROMPT_LINE_CAP) -> str:
    """Numbered lines as the model sees them: one number, one bar, one line.

    The numbers are given rather than counted, because the second pass asks
    about a shortlist -- lines 12, 400 and 9,981 of a capture, with nothing
    between them. They have to keep the numbers they had there, or an answer
    about the shortlist would name lines of the capture nobody asked about.
    """
    out = []
    for number, line in pairs:
        shown = line if len(line) <= cap else line[:cap] + " …"
        out.append(f"{number}| {shown}")
    return "\n".join(out)


def numbered(lines: list[str], first: int = 1, cap: int = PROMPT_LINE_CAP) -> str:
    """A consecutive run of lines, numbered from `first`."""
    return rows(enumerate(lines, first), cap)


def ceiling(budget: int, asks: int) -> str:
    """One ask's share of what the whole view may cost.

    Divided, and this is the whole of Faz 8. The budget was a sentence in one
    question before, and a capture split into five asks was five times told to
    keep a hundred lines -- so it kept five hundred, and the tool that promised
    to cost a page cost a chapter. A share holds: five asks for twenty-four lines
    each answer the same size as one ask for a hundred and twenty, and the view
    costs what it costs whether the build printed four hundred lines or ten
    thousand.

    Written here beside the parser for the reason `ANSWER_FORMAT` is written
    here: two questions must not be able to say this two different ways.
    """
    each = max(1, budget // asks)
    word = "line" if each == 1 else "lines"
    return (
        f"\nKeep the answer to about {each} {word}. If more than that would "
        "qualify, answer with the ones that carry the most and leave the rest "
        "out; nothing is lost by leaving a line out, because the whole text is "
        "on disk and can be asked for by number afterwards.\n"
    )


def read_numbers(answer: str, total: int) -> set[int]:
    """Every line number in the model's reply, and nothing else from it.

    Prose around the numbers is ignored rather than rejected: a model that
    explains itself has still answered the question, and the explanation is the
    part that cannot be trusted. Numbers outside the capture are dropped -- a
    line that does not exist cannot be shown, and inventing one is exactly what
    this design exists to prevent.
    """
    chosen: set[int] = set()
    for low, high, single in _NUMBERS.findall(answer):
        if single:
            start = end = int(single)
        else:
            start, end = sorted((int(low), int(high)))
        start = max(start, 1)
        end = min(end, total)
        chosen.update(range(start, end + 1))
    return chosen


def runs(chosen: set[int]) -> list[tuple[int, int]]:
    """The chosen numbers as consecutive stretches, in order."""
    stretches: list[tuple[int, int]] = []
    for number in sorted(chosen):
        if stretches and number == stretches[-1][1] + 1:
            stretches[-1] = (stretches[-1][0], number)
        else:
            stretches.append((number, number))
    return stretches


def gap(count: int, handle: str) -> str:
    """The mark left where lines were folded away.

    It says how many, and how to read them. A view that hid things silently
    would be asking to be trusted; this one can be checked.
    """
    word = "line" if count == 1 else "lines"
    return f"─ {count:,} {word} not shown · sift peek {handle} for any of them ─"


def render(lines: list[str], chosen: set[int], handle: str) -> str:
    """The view: chosen lines exactly as captured, gaps marked with their size."""
    pieces: list[str] = []
    previous_end = 0
    for start, end in runs(chosen):
        if start > previous_end + 1:
            pieces.append(gap(start - previous_end - 1, handle))
        pieces.extend(lines[start - 1 : end])
        previous_end = end
    if previous_end < len(lines):
        pieces.append(gap(len(lines) - previous_end, handle))
    return "\n".join(pieces)


def select(
    lines: list[str],
    question: str,
    handle: str,
    bridge: Bridge | None = None,
    budget: int | None = BUDGET,
) -> View | None:
    """Ask one question about numbered lines, and show the ones it answers with.

    The question is an argument because nothing underneath it is about failures.
    Numbering the lines, cutting a long text into asks that keep their original
    numbering, reading numbers out of a reply and discarding the rest, printing
    from the source byte for byte -- none of that changes when the question
    changes from *what went wrong here* to *what is declared here*. Only the
    sentence changes, and a second sentence is not a second engine.

    The prompt is assembled here and not by the caller: the question, then what
    the answer may cost, then how to write it. A question that carried its own
    budget could only state it per ask, and would be right about one ask and
    wrong about the capture.

    Returns nothing when there is no usable judgement -- no key, no model that
    would answer, or an answer with no numbers in it. The caller decides what to
    do with that; falling back is not this function's business, and pretending to
    have judged would be worse than admitting it did not.
    """
    if not lines:
        return View(handle, "", 0, 0, None, 0)

    judge = bridge if bridge is not None else Bridge()
    batches = _batches(list(enumerate(lines, 1)))
    asked = prompt(question, budget, len(batches))
    chosen: set[int] = set()
    model: str | None = None
    unanswered = 0
    asks = 0

    for answer in _ask_all(judge, asked, batches):
        asks += 1
        if answer is None:
            unanswered += 1
            continue
        model = answer.model
        chosen |= read_numbers(answer.text, len(lines))

    if not chosen:
        return None

    if budget is not None and len(chosen) > budget:
        chosen, spent = narrow(lines, chosen, question, budget, judge)
        asks += spent

    return View(
        handle=handle,
        text=render(lines, chosen, handle),
        kept=len(chosen),
        total=len(lines),
        model=model,
        asks=asks,
        unanswered=unanswered,
    )


def narrow(
    lines: list[str],
    chosen: set[int],
    question: str,
    budget: int,
    judge: Bridge,
) -> tuple[set[int], int]:
    """Hand an over-long answer back and ask which part of it to keep.

    The alternative was to cut it here, and cutting means ranking lines with code
    that cannot read them. Every rule available is wrong somewhere: drop the
    short runs and a lone `FAILED` goes, drop the long ones and a stack trace
    goes, drop from the middle and it is a coin toss. The model ranked these
    lines once. Shown a shorter list it can rank them again, the reply is still
    numbers, and the guarantee the whole tool rests on does not move.

    What is asked is the original question plus `NARROWING`, and not the
    original question on its own -- that was measured, and it comes back with the
    shortlist unchanged, because a list of lines that all matter is a correct
    answer to a question about which lines matter.

    Only lines already chosen survive a round: a number from outside the
    shortlist is dropped rather than admitted, so narrowing can never widen. A
    round that comes back empty leaves the previous answer standing, because a
    question nobody answered is not a decision to show nothing. And a round that
    changes nothing ends it -- asking a fourth time costs what the first three
    cost and has already been refused three times.
    """
    asks = 0
    for _ in range(NARROW_ROUNDS):
        if len(chosen) <= budget:
            break
        shortlist = [(number, lines[number - 1]) for number in sorted(chosen)]
        batches = _batches(shortlist)
        asked = prompt(question + NARROWING, budget, len(batches))
        kept: set[int] = set()
        for batch in batches:
            answer = judge.ask(asked, rows(batch), max_tokens=2048)
            asks += 1
            if answer is not None:
                kept |= read_numbers(answer.text, len(lines)) & chosen
        if not kept or len(kept) >= len(chosen):
            break
        chosen = kept
    return chosen, asks


def prompt(question: str, budget: int | None, asks: int) -> str:
    """The question, what the answer may cost, and how to write it -- in order."""
    share = ceiling(budget, asks) if budget is not None else ""
    return question + share + ANSWER_FORMAT


def distill(capture: Capture, bridge: Bridge | None = None) -> View | None:
    """Ask which lines of a capture matter, then show those lines from it."""
    return select(text_lines.of(capture.text()), QUESTION, capture.handle, bridge)


def _ask_all(
    judge: Bridge, asked: str, batches: list[list[tuple[int, str]]]
) -> list[Answer | None]:
    """Every piece of one capture, asked about at the same time.

    The pieces do not overlap and their answers are added together as a set, so
    the order the replies arrive in cannot change what comes back -- only how
    long it takes. One piece is asked about directly rather than through a pool,
    because a pool for one job is a thread and a queue to do what a call does.

    `narrow` is deliberately left serial. Each of its rounds is a question about
    the previous round's answer, so there is nothing there to overlap.

    The bridge is shared across the threads, which is safe for everything it
    holds except `last_error`: two pieces failing at once leave one of the two
    reasons behind rather than both. Both are true, and the caller shows one.
    """
    if len(batches) == 1:
        return [judge.ask(asked, rows(batches[0]), max_tokens=2048)]
    with ThreadPoolExecutor(max_workers=min(workers(), len(batches))) as pool:
        return list(
            pool.map(lambda batch: judge.ask(asked, rows(batch), max_tokens=2048), batches)
        )


def _batches(pairs: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    """Numbered lines in pieces small enough to ask about, keeping their numbers.

    Splitting never renumbers: a piece that starts at line 4,001 is numbered from
    4,001, so an answer about it needs no translation and cannot be misread as
    being about the top of the file. The numbers arrive with the lines rather
    than being counted from an offset here, which is what lets the second pass
    reuse this on a shortlist whose lines are nowhere near each other.
    """
    batches: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    size = 0
    for number, line in pairs:
        cost = min(len(line), PROMPT_LINE_CAP) + 12
        if current and size + cost > CHARS_PER_ASK:
            batches.append(current)
            current = []
            size = 0
        current.append((number, line))
        size += cost
    batches.append(current)
    return batches
