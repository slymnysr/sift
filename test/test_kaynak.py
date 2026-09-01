"""Faz 6 -- the source corpus, and what can be checked about it without a model.

Faz 5 asked whether the choice survives the human language a log is written in.
This asks the harder half of the same question: whether it survives the
programming language a file is written in, when nothing in `sift` has ever been
told that programming languages exist.

The design being replaced answered that with a table -- one entry per language,
keyed on the file's suffix and its bare name. Every sample here is stored as
`.txt`, whatever it is written in. That is not tidiness. It is the measurement
being made honest: a corpus where the Rust sample were called `.rs` could not
tell a model that reads Rust apart from a table that recognises `.rs`, so it
could not have tested anything. Under `.txt`, a suffix table scores zero and
only reading the file can score anything at all.

Whether the reading is any good needs a network, so it lives in
`test/outlines.py`. Everything around it is checked here, offline, every run.
"""

from __future__ import annotations

import pytest

import korpus_reader as k
from sift import lines as text_lines
from sift import outline as o
from sift.model import Answer

SAMPLES = k.every(k.KAYNAK)
BY_NAME = {s.name: s for s in SAMPLES}


class _Chooser:
    """A judge that answers with the numbers it was told to answer with.

    It cannot stand in for the model's judgement about what a declaration is,
    and does not try to. It is here so the machinery between the file and the
    screen can be checked once per language.
    """

    def __init__(self, chosen) -> None:
        self.chosen = chosen
        self.seen: list[tuple[str, str]] = []

    def ask(self, system: str, user: str, *, max_tokens: int = 1024):
        self.seen.append((system, user))
        return Answer(text=", ".join(str(n) for n in self.chosen), model="test", tries=1)


def _path(sample: k.Sample):
    return k.path_of(sample)


# -- is the corpus well formed? ---------------------------------------------


def test_every_sample_has_labels_and_every_label_has_a_sample():
    stems = {p.stem for p in k.KAYNAK.glob("*.txt")}
    labelled = {p.stem for p in k.KAYNAK.glob("*.json")}
    assert stems == labelled, f"eslesmeyen: {stems ^ labelled}"
    assert stems, "kaynak korpusu bos"


def test_no_sample_carries_its_language_in_its_suffix():
    """The claim of the phase, made structural before anything is measured.

    Fourteen languages, one extension. Nothing that reads the name of a file can
    score above zero on this corpus, so anything that does score is reading the
    file.
    """
    suffixes = {p.suffix for p in k.KAYNAK.iterdir()}
    assert suffixes == {".txt", ".json"}, sorted(suffixes)


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.name)
def test_the_reader_and_the_outline_see_the_same_file(sample):
    """Both sides count lines the one way, or every label points at other text."""
    assert o.read(_path(sample)) == sample.body
    assert sample.claimed_lines == sample.total


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.name)
def test_every_labelled_line_exists_and_says_something(sample):
    assert sample.must_show, f"{sample.name}: bildirim satiri yok"
    for number in sample.must_show:
        assert 1 <= number <= sample.total, f"{sample.name}: {number} disarida"
        assert sample.line(number).strip(), (
            f"{sample.name}: {number}. satir bos, bildirim olamaz"
        )
    for number in sample.noise:
        assert 1 <= number <= sample.total, f"{sample.name}: govde {number} disarida"


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.name)
def test_no_line_is_both_a_declaration_and_a_body(sample):
    both = set(sample.must_show) & sample.noise
    assert not both, f"{sample.name}: {sorted(both)} hem bildirim hem govde"


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.name)
def test_every_sample_says_which_kind_of_corpus_it_belongs_to(sample):
    assert sample.kind == "source", f"{sample.name}: kind={sample.kind!r}"
    assert sample.family, f"{sample.name}: sozdizim ailesi yazilmamis"


def test_the_corpus_is_broad_enough_to_be_evidence():
    """A corpus of C-like languages would prove almost nothing.

    The floors are on syntax families rather than on languages, because a
    declaration in Haskell, in Make and in Lisp does not look like a declaration
    in Java in any way a regular expression could share. Twelve languages spread
    over six families is where the table stops being replaceable by a longer
    table.
    """
    languages = {s.language for s in SAMPLES}
    families = {s.family for s in SAMPLES}
    assert len(languages) >= 12, sorted(languages)
    assert len(families) >= 6, sorted(families)
    assert sum(len(s.must_show) for s in SAMPLES) >= 100
    assert sum(len(s.noise) for s in SAMPLES) >= 100


def test_the_corpus_contains_a_language_no_table_could_ever_have_held():
    """One sample nobody can look up, so nobody can have prepared for it.

    Every other sample is a language a careful table might have covered. This
    one was invented for the corpus: it has no compiler, no documentation and no
    entry anywhere. If the outline finds its declarations, it found them by
    reading.
    """
    made_up = [s for s in SAMPLES if s.family == "invented"]
    assert made_up, "uydurma dil ornegi yok"
    for sample in made_up:
        assert "def " not in sample.text
        assert "function" not in sample.text


def test_the_families_that_a_brace_rule_would_miss_are_all_present():
    """The syntaxes that broke the old design are the ones worth naming.

    `end` keywords, equations with no delimiter at all, tab-significant Make
    rules and parenthesised Lisp are exactly the shapes a `defines` regular
    expression written for braces gets wrong.
    """
    families = {s.family for s in SAMPLES}
    for needed in ("braces", "indent", "end", "equations", "declarative", "parens"):
        assert needed in families, f"{needed} ailesinden ornek yok"


# -- does anything between the file and the screen read the language? -------


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.name)
def test_the_outline_is_the_file_in_every_language(sample):
    """Given the right numbers, every declaration comes back byte for byte."""
    view = o.outline(_path(sample), _Chooser(sample.must_show))
    assert view is not None
    assert view.total == sample.total
    assert view.kept == len(sample.must_show)
    shown = view.text.split("\n")
    for number in sample.must_show:
        assert sample.line(number) in shown, f"{sample.name}: {number}. satir kayip"


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.name)
def test_the_prompt_carries_the_file_and_never_the_file_name(sample):
    """Nothing that could hint at the language reaches the model but the text.

    Not the path, not the sample's name, not the word for the language it is
    written in. The old design would have had to send at least the suffix.
    """
    judge = _Chooser(sample.must_show)
    o.outline(_path(sample), judge)
    system, asked = judge.seen[-1]
    assert system.startswith(o.QUESTION)
    for leak in (sample.name, str(_path(sample)), _path(sample).name):
        assert leak not in asked, f"{sample.name}: istem {leak!r} sizdirdi"
    numbered_lines = text_lines.of(asked)
    assert len(numbered_lines) == sample.total
    for offset, line in enumerate(numbered_lines, 1):
        number, _, text = line.partition("| ")
        assert int(number) == offset
        assert sample.line(offset).startswith(text.removesuffix(" …"))


def test_every_language_in_the_corpus_is_asked_the_same_question():
    """One question, fourteen languages -- because there is nothing to vary.

    A table would have to choose which entry applies before it could look at
    the file. Here there is nothing to choose, and this is what that looks like
    from the outside.
    """
    asked = set()
    for sample in SAMPLES:
        judge = _Chooser(sample.must_show)
        o.outline(_path(sample), judge)
        asked.add(judge.seen[-1][0])
    assert len(asked) == 1


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.name)
def test_the_safety_net_never_writes_a_line_in_any_language(sample):
    """With no model at all, every line shown is still a line from the file."""
    view = o.ends_of(_path(sample))
    known = set(sample.body)
    for line in view.text.split("\n"):
        assert line in known or "not shown · sift peek" in line, (
            f"{sample.name}: yedek dosyada olmayan bir satir yazdi: {line!r}"
        )
