"""Faz 5 -- the corpus, and everything about it that can be checked without a model.

The claim this phase exists to test is that coverage is not a list: that a
Swahili identifier, a Hebrew test name and a mainframe job log go through the
same code as an English pytest run, because nothing in that code knows what any
of them are. Deciding whether the *choice* is as good in Vietnamese as in
English needs a model and a network, so it lives in `test/languages.py` and is
run on purpose.

Everything around the choice can be checked here, offline, on every run: that
the corpus is well formed, that its labels point at real lines, and that no part
of the pipeline other than the model behaves differently for one script than
for another.
"""

from __future__ import annotations

import pytest

import budget as b
import korpus_reader as k
from sift import lines as text_lines
from sift.distill import View, distill, numbered
from sift.fallback import fallback
from sift.model import Answer

SAMPLES = k.every()
BY_NAME = {s.name: s for s in SAMPLES}


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFT_HOME", str(tmp_path / "sift"))


class _Chooser:
    """A judge that answers with the numbers it was told to answer with.

    It stands in for the model so that the rest of the pipeline can be checked
    on every sample without a network. It cannot stand in for the model's
    judgement, and does not try to -- that is what `test/languages.py` measures.
    """

    def __init__(self, chosen) -> None:
        self.chosen = chosen
        self.seen: list[str] = []

    def ask(self, system: str, user: str, *, max_tokens: int = 1024):
        self.seen.append(user)
        return Answer(text=", ".join(str(n) for n in self.chosen), model="test", tries=1)


# -- is the corpus well formed? ---------------------------------------------


def test_every_sample_has_labels_and_every_label_has_a_sample():
    stems = {p.stem for p in k.KORPUS.glob("*.txt")}
    labelled = {p.stem for p in k.KORPUS.glob("*.json")}
    assert stems == labelled, f"eslesmeyen: {stems ^ labelled}"
    assert stems, "korpus bos"


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.name)
def test_the_labelled_line_count_is_the_count_the_code_sees(sample):
    """The one number that ties every label to the code that reads it.

    Every other label is a line number, and a line number only means something
    if both sides agree on where the lines are. If this ever fails, no other
    label in that sample can be trusted either.
    """
    assert sample.claimed_lines == sample.total


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.name)
def test_every_labelled_line_exists_and_says_something(sample):
    assert sample.must_show, f"{sample.name}: gorulmesi gereken satir yok"
    for number in sample.must_show:
        assert 1 <= number <= sample.total, f"{sample.name}: {number} disarida"
        assert sample.line(number).strip(), (
            f"{sample.name}: {number}. satir bos, gorulmesi gerekemez"
        )
    for number in sample.noise:
        assert 1 <= number <= sample.total, f"{sample.name}: gurultu {number} disarida"


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.name)
def test_no_line_is_both_required_and_noise(sample):
    both = set(sample.must_show) & sample.noise
    assert not both, f"{sample.name}: {sorted(both)} hem gerekli hem gurultu"


def test_the_corpus_is_broad_enough_to_be_evidence():
    """A corpus of five English samples would prove nothing about the claim.

    These floors are not arbitrary. Six scripts is the point at which the
    alphabet stops being an accident of the sample. Twenty tools is past the
    number any hand-written list of languages ever managed to cover.
    """
    languages = {s.language for s in SAMPLES}
    scripts = {s.script for s in SAMPLES}
    tools = {s.tool for s in SAMPLES}
    assert len(languages) >= 18, sorted(languages)
    assert len(scripts) >= 6, sorted(scripts)
    assert len(tools) >= 20, sorted(tools)
    assert sum(1 for s in SAMPLES if not s.failed) >= 3, "hepsi hata; basari da olcuulmeli"
    assert sum(1 for s in SAMPLES if s.failed) >= 15


def test_the_corpus_contains_output_python_would_miscount():
    """At least one sample carries the characters the line rule exists for.

    A rule with nothing in the corpus that exercises it is a rule that will be
    quietly reverted one day and nobody will notice.
    """
    risky = [s for s in SAMPLES if any(c in s.text for c in ("\x0c", "\x85", "\r"))]
    assert risky, "hicbir ornek satir kuralini sinamiyor"
    for sample in risky:
        assert len(sample.text.splitlines()) > sample.total, (
            f"{sample.name}: str.splitlines() ayni sayiyi veriyor, ornek bos yere duruyor"
        )


# -- does the pipeline read the language? -----------------------------------


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.name)
def test_the_view_is_the_capture_in_every_script(sample):
    """Given the right numbers, every required line comes back byte for byte.

    This is the guarantee of Faz 3 checked once per script rather than once. The
    model is taken out of it on purpose: what is being tested is that nothing
    between the file and the screen has an opinion about alphabets.
    """
    capture = k.as_capture(sample)
    view = distill(capture, _Chooser(sample.must_show))
    assert view is not None
    assert view.total == sample.total
    assert view.kept == len(sample.must_show)
    shown = view.text.split("\n")
    for number in sample.must_show:
        assert sample.line(number) in shown, f"{sample.name}: {number}. satir kayip"


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.name)
def test_the_prompt_shows_the_model_the_capture_and_nothing_else(sample):
    capture = k.as_capture(sample)
    judge = _Chooser(sample.must_show)
    distill(capture, judge)
    asked = text_lines.of("\n".join(judge.seen))
    assert len(asked) == sample.total
    for offset, line in enumerate(asked, 1):
        number, _, text = line.partition("| ")
        assert int(number) == offset
        assert sample.line(offset).startswith(text.removesuffix(" …"))


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.name)
def test_the_safety_net_never_writes_a_line_in_any_script(sample):
    """With no model at all, every line shown is still a line that was captured."""
    view = fallback(k.as_capture(sample))
    known = set(sample.body)
    for line in view.text.split("\n"):
        assert line in known or "not shown · sift peek" in line, (
            f"{sample.name}: yedek yakalanmayan bir satir yazdi: {line!r}"
        )


def test_a_capture_read_as_text_would_not_be_the_same_capture():
    """Why the corpus is read as bytes, shown on the sample that proves it.

    `read_text` turns on universal newlines. The progress bar in this sample
    redraws itself six times; read as text those become six lines that were
    never written, and every label below them would point at the wrong place.
    """
    sample = BY_NAME["ansi-progress"]
    as_text = (k.KORPUS / "ansi-progress.txt").read_text(encoding="utf-8")
    assert len(text_lines.of(as_text)) > sample.total
    assert "\r" in sample.text


def test_numbering_a_sample_never_moves_a_line():
    """Numbering is done on the same list `peek` would answer from."""
    sample = BY_NAME["cobol-mainframe"]
    lines = text_lines.of(numbered(sample.body))
    assert len(lines) == sample.total
    assert lines[-1] == f"{sample.total}| {sample.line(sample.total)}"


# -- Faz 8: what the measurement is allowed to blame the ceiling for ---------

def test_a_sample_the_endpoint_never_answered_for_is_left_out_of_the_row():
    """Its required lines were not lost to the ceiling. Nobody looked for them.

    Counted into the row, an unanswered sample lowers the score of whichever
    budget happened to be running when a free endpoint was busy -- which is how
    the first pinned run reported the default budget as a bug.
    """
    sample = k.every()[0]
    row = b.Row(b.BUDGET)

    b._fold(row, sample, View(sample.name, "", 0, 0, "a-model", 3, unanswered=2))

    assert row.counted == 0
    assert row.required == 0, "an unanswered sample must not lower the score"
    assert row.silent == [f"{sample.name}: 2/3 unanswered"]


def test_a_sample_with_no_answer_at_all_is_left_out_the_same_way():
    sample = k.every()[0]
    row = b.Row(b.BUDGET)

    b._fold(row, sample, None)

    assert row.counted == 0
    assert row.required == 0
    assert row.silent == [f"{sample.name}: no answer at all"]


def test_a_sample_that_was_answered_for_is_counted_and_scored():
    sample = k.every()[0]
    row = b.Row(b.BUDGET)
    shown = "\n".join(sample.line(n) for n in sample.must_show)

    b._fold(row, sample, View(sample.name, shown, len(sample.must_show), 99, "a-model", 1))

    assert row.counted == 1
    assert row.silent == []
    assert row.found == row.required == len(sample.must_show)



def _row(budget, missed):
    return b.Row(budget, missed=list(missed))


def test_a_line_lost_with_and_without_a_ceiling_is_not_charged_to_the_ceiling():
    """The corpus loses some lines at every setting. That is the model, not the sum.

    A report that charged them to the default budget would fail the build over a
    judgement nobody changed, and the one number the build is watching would stop
    meaning anything.
    """
    both = ["gradle-ko 32: BUILD FAILED"]
    cost, anyway = b.verdict([_row(b.BUDGET, both), _row(None, both)])

    assert cost == []
    assert anyway == ["gradle-ko 32: BUILD FAILED"]


def test_a_line_only_the_ceiling_loses_is_charged_to_the_ceiling():
    cost, anyway = b.verdict(
        [
            _row(b.BUDGET, ["gotest-zh 8: === RUN"]),
            _row(None, ["gradle-ko 32: BUILD FAILED"]),
        ]
    )

    assert cost == ["gotest-zh 8: === RUN"]
    assert anyway == []


def test_with_nothing_to_compare_against_every_miss_is_the_ceilings():
    """`budget.py 120` has no unbounded row, so nothing can be ruled out."""
    cost, anyway = b.verdict([_row(b.BUDGET, ["gradle-ko 32: BUILD FAILED"])])

    assert cost == ["gradle-ko 32: BUILD FAILED"]
    assert anyway == []


def test_a_run_without_the_default_budget_has_nothing_to_say_about_it():
    assert b.verdict([_row(20, ["latex-pl 32: ! Emergency stop."])]) == ([], [])
