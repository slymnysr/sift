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

import contextlib
import os
import re
import threading
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from sift import answers, records
from sift import lines as text_lines
from sift.capture import Capture
from sift.model import Answer, Bridge
from sift.privacy import mask

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

# What to ask when the text was a list rather than a transcript.
#
# The shape of the answer does not change -- numbers, and nothing else -- and
# neither does anything under it. What changes is what the numbers count, and
# saying so is the whole of the difference: asked "which lines matter" about a
# list, a model answers about lines that do not exist as units.
#
# The last sentence is the one a transcript does not need. A reader of a log
# wants the exceptional lines and nothing else; a reader of a list of four
# hundred records also needs to know what the ordinary ones look like, or the
# view says a list is made of nothing but its outliers.
RECORDS = (
    "You are given the records of a JSON array, numbered one per record.\n"
    "Choose the records someone would need to understand this list: what failed, "
    "what is unusual, what marks a boundary or a change.\n"
    "Leave out records that say the same thing another one already says, but keep "
    "a few ordinary ones, so that what the rest look like can be seen.\n"
)

# What to ask about the part of a command that has arrived since the last look.
#
# The difference from `QUESTION` is not tone, it is what is true. There is no
# final result yet, and asking for one invites a model to nominate whichever
# line happens to be nearest the end. And the reader has already been shown
# everything before these lines, so a line that repeats what they read ten
# minutes ago is worth less here than the same line would be in a capture read
# once, at the end, by someone who was not watching.
FOLLOWING = (
    "You are given the numbered output a command has produced since it was last "
    "looked at. The command is still running: this is the middle of the output, "
    "not the end of it, and there is no final result here to find.\n"
    "Choose the lines that tell someone watching what has happened since they "
    "last looked: what failed, what warned, what finished, what changed.\n"
    "Leave out progress that only says work is still going on. If nothing here "
    "is worth interrupting them for, choose nothing at all.\n"
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
    # What `kept` and `total` are counting. A line, unless the text was a JSON
    # array, in which case a line was never a unit and a record is. Carried on
    # the view rather than worked out again by whoever prints it: two places
    # deciding this separately is two places that can disagree about what a
    # number means, and the number is the whole of what a footer says.
    unit: str = "line"

    @property
    def folded(self) -> int:
        return self.total - self.kept


def rows(pairs: Iterable[tuple[int, str]], cap: int = PROMPT_LINE_CAP) -> str:
    """Numbered lines as the model sees them: one number, one bar, one line.

    The numbers are given rather than counted, because the second pass asks
    about a shortlist -- lines 12, 400 and 9,981 of a capture, with nothing
    between them. They have to keep the numbers they had there, or an answer
    about the shortlist would name lines of the capture nobody asked about.

    This is the only place capture text is turned into something that leaves the
    machine, which is why the masking happens here and nowhere else. What is
    shown to the reader is rendered somewhere else entirely, from the file, and
    is never touched by it.
    """
    out = []
    for number, line in pairs:
        # Masked before it is shortened, not after. Half a secret is still a
        # secret, and a pattern cannot recognise the half it is shown.
        safe = mask(line)
        shown = safe if len(safe) <= cap else safe[:cap] + " …"
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


def read_numbers(answer: str, total: int, first: int = 1) -> set[int]:
    """Every line number in the model's reply, and nothing else from it.

    Prose around the numbers is ignored rather than rejected: a model that
    explains itself has still answered the question, and the explanation is the
    part that cannot be trusted. Numbers outside the capture are dropped -- a
    line that does not exist cannot be shown, and inventing one is exactly what
    this design exists to prevent.

    `first` is where the numbering starts, which is 1 for a whole capture and
    the line after the last one already read for a command still running. The
    bound moves with it: a model shown lines 812 to 900 that answers "4" is
    answering about a line nobody showed it.
    """
    chosen: set[int] = set()
    for low, high, single in _NUMBERS.findall(answer):
        if single:
            start = end = int(single)
        else:
            start, end = sorted((int(low), int(high)))
        start = max(start, first)
        end = min(end, first + total - 1)
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


def gap(count: int, handle: str, unit: str = "line") -> str:
    """The mark left where units were folded away.

    It says how many, and how to read them. A view that hid things silently
    would be asking to be trusted; this one can be checked.

    `peek` is addressed in lines, so the sentence changes with the unit rather
    than pretending records can be asked for by number. What it points at is the
    same capture either way, and that is what the second rule promises: not that
    every unit has an address, but that nothing was thrown away.
    """
    word = unit if count == 1 else unit + "s"
    if unit == "line":
        return f"─ {count:,} {word} not shown · sift peek {handle} for any of them ─"
    return f"─ {count:,} {word} not shown · sift peek {handle} for the text they came from ─"


def render(
    lines: list[str],
    chosen: set[int],
    handle: str,
    first: int = 1,
    unit: str = "line",
) -> str:
    """The view: chosen lines exactly as captured, gaps marked with their size.

    Nothing before `first` is marked as a gap. For a whole capture there is
    nothing before it; for a command still running, what came before was already
    handed to the reader in an earlier look, and marking it "not shown" would be
    telling them they missed something they have already been given.
    """
    pieces: list[str] = []
    previous_end = first - 1
    for start, end in runs(chosen):
        if start > previous_end + 1:
            pieces.append(gap(start - previous_end - 1, handle, unit))
        pieces.extend(lines[start - first : end - first + 1])
        previous_end = end
    last = first + len(lines) - 1
    if previous_end < last:
        pieces.append(gap(last - previous_end, handle, unit))
    return "\n".join(pieces)


def select(
    lines: list[str],
    question: str,
    handle: str,
    bridge: Bridge | None = None,
    budget: int | None = BUDGET,
    first: int = 1,
    keep: str | None = None,
    unit: str = "line",
) -> View | None:
    """Ask one question about numbered units, and show the ones it answers with.

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

    `first` is the number the first of these lines has in the capture it came
    from, which is 1 unless the caller is looking at the part of a running
    command it has not looked at yet. It is a number and not a slice because
    every number that leaves here ends up in `sift peek`: a view whose numbers
    started over at 1 would send the reader to the wrong line of a file that
    disagrees with them, which is the one thing this tool promises cannot
    happen.

    `keep` is the caller's own say: any line matching it is shown, whatever the
    model chose and whatever the ceiling allows. `_always` explains why a pattern
    is permitted to exist here when `fallback` refuses them outright.

    Returns nothing when there is no usable judgement -- no key, no model that
    would answer, or an answer with no numbers in it. The caller decides what to
    do with that; falling back is not this function's business, and pretending to
    have judged would be worse than admitting it did not. A `keep` that matched
    something is judgement enough on its own: those lines were asked for by name,
    so they come back even when nobody answered.
    """
    if not lines:
        return View(handle, "", 0, 0, None, 0, unit=unit)

    always = _always(lines, keep, first) if keep else set()

    named = answers.key("\n".join(lines), question, budget, first)
    remembered = answers.load(named) if answers.wanted() else None
    if remembered is not None:
        return _seen(lines, remembered, always, handle, first, unit)

    judge = bridge if bridge is not None else Bridge()
    batches = _batches(list(enumerate(lines, first)))
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
        chosen |= read_numbers(answer.text, len(lines), first)

    if not chosen and not always:
        return None

    if budget is not None and len(chosen) > budget:
        chosen, spent = narrow(lines, chosen, question, budget, judge, first)
        asks += spent

    # Written after narrowing and before `keep`, so what is remembered is the
    # model's judgement under this ceiling and nothing the caller added to it.
    # `keep` is applied again on the way out of a hit, because it is an
    # instruction rather than an answer and belongs to the call, not the cache.
    if answers.wanted():
        answers.save(named, chosen, model, unanswered)

    chosen = chosen | always

    return View(
        handle=handle,
        text=render(lines, chosen, handle, first, unit),
        kept=len(chosen),
        total=len(lines),
        model=model,
        asks=asks,
        unanswered=unanswered,
        unit=unit,
    )


def _seen(
    lines: list[str],
    remembered: answers.Answered,
    always: set[int],
    handle: str,
    first: int,
    unit: str,
) -> View:
    """A view built from an answer already given, rendered against this text.

    `asks` is zero and that is the whole of what was saved. It is also how a
    reader is told: a view naming a model and costing no questions is one that
    was remembered, and the footer says so rather than implying a model was
    reached just now.
    """
    chosen = remembered.chosen | always
    return View(
        handle=handle,
        text=render(lines, chosen, handle, first, unit),
        kept=len(chosen),
        total=len(lines),
        model=remembered.model,
        asks=0,
        unanswered=remembered.unanswered,
        unit=unit,
    )


def _always(lines: list[str], keep: str, first: int) -> set[int]:
    """The lines the caller named, whatever the model made of them.

    This is the only pattern anywhere in the judging path, and it is allowed
    because it is not this tool's pattern. A rule invented here about what output
    looks like would be a guess about languages it half knows, wearing the
    clothes of knowledge -- the thing `fallback` refuses in the strongest terms.
    A pattern the caller typed is not a guess: they know what they are looking
    for, and the only job left is to not lose it.

    A pattern that will not compile is used as plain text. Someone who typed
    `main()` meant those characters, and answering a mistyped group with silence
    would drop the request without ever saying so.
    """
    try:
        found = re.compile(keep)
    except re.error:
        return {n for n, line in enumerate(lines, first) if keep in line}
    return {n for n, line in enumerate(lines, first) if found.search(line)}


def narrow(
    lines: list[str],
    chosen: set[int],
    question: str,
    budget: int,
    judge: Bridge,
    first: int = 1,
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
        shortlist = [(number, lines[number - first]) for number in sorted(chosen)]
        batches = _batches(shortlist)
        asked = prompt(question + NARROWING, budget, len(batches))
        kept: set[int] = set()
        for batch in batches:
            answer = ask_one(judge, asked, batch)
            asks += 1
            if answer is not None:
                kept |= read_numbers(answer.text, len(lines), first) & chosen
        if not kept or len(kept) >= len(chosen):
            break
        chosen = kept
    return chosen, asks


def prompt(question: str, budget: int | None, asks: int) -> str:
    """The question, what the answer may cost, and how to write it -- in order."""
    share = ceiling(budget, asks) if budget is not None else ""
    return question + share + ANSWER_FORMAT


def distill(
    capture: Capture,
    bridge: Bridge | None = None,
    budget: int | None = BUDGET,
    keep: str | None = None,
) -> View | None:
    """Ask which parts of a capture matter, then show those parts from it.

    The unit is decided here and nowhere else, by asking the text rather than by
    asking what produced it. A command that prints a JSON array is not a
    different kind of command and there is no list here of the ones that do it;
    `records.of` either finds an array or does not, and that answer is a fact
    about the bytes.
    """
    text = capture.text()
    found = records.of(text)
    if found is not None:
        return select(
            found,
            RECORDS,
            capture.handle,
            bridge,
            budget=budget,
            keep=keep,
            unit="record",
        )
    return select(
        text_lines.of(text),
        QUESTION,
        capture.handle,
        bridge,
        budget=budget,
        keep=keep,
    )


def follow(
    lines: list[str],
    handle: str,
    first: int,
    bridge: Bridge | None = None,
) -> View | None:
    """Ask which of a running command's newest lines matter, and show those.

    The same engine as `distill`, with the two things that are actually
    different made different: the question knows the output has not ended, and
    the numbering starts where the reader's last look stopped instead of at 1.
    """
    return select(lines, FOLLOWING, handle, bridge, first=first)


_GATE: dict[int, threading.Semaphore] = {}
_GATE_LOCK = threading.Lock()


@contextlib.contextmanager
def in_flight() -> Iterator[None]:
    """One ceiling on asks in the air, wherever in this process they started.

    `SIFT_WORKERS` is a statement about this machine and this endpoint: how many
    requests may be outstanding at once. It used to be read at two levels -- how
    many samples to measure at a time, and how many pieces of one sample to ask
    about at a time -- with nothing tying them together, so they multiplied. Six
    became thirty-six, the free endpoint refused what it could not take, and the
    refusals were counted as lines this tool had lost. That is written up in
    `notlar/08`, and it cost a day.

    Phase 15 makes the multiplying easy again: several files, several running
    commands, each of them split into pieces. So the ceiling stopped being
    arithmetic every caller has to redo, and became a gate every ask goes
    through. A number that is enforced in one place cannot be multiplied by a
    caller who did not know about it.

    The gate is rebuilt when the setting changes, which is what makes it usable
    from a test. Asks already through an older gate are still governed by it --
    they finish under the ceiling they started under, which is the only sense in
    which "changed the limit" can mean anything mid-flight.
    """
    size = workers()
    with _GATE_LOCK:
        gate = _GATE.get(size)
        if gate is None:
            gate = _GATE[size] = threading.Semaphore(size)
    gate.acquire()
    try:
        yield
    finally:
        gate.release()


def ask_one(judge: Bridge, asked: str, batch: list[tuple[int, str]]) -> Answer | None:
    """One question, through the gate. Every ask in this file goes through here."""
    with in_flight():
        return judge.ask(asked, rows(batch), max_tokens=2048)


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
        return [ask_one(judge, asked, batches[0])]
    with ThreadPoolExecutor(max_workers=min(workers(), len(batches))) as pool:
        return list(pool.map(lambda batch: ask_one(judge, asked, batch), batches))


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
