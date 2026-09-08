"""Faz 22 -- the same question, asked twice.

The cache is off for every other test in this suite, on purpose: they measure
what happens when the question is asked, and something that quietly answers
instead turns those into measurements of nothing. So it is turned back on here,
where it is the thing being measured.

Two claims, and the second is the one that would be easy to get wrong. That a
second identical ask costs no request. And that a remembered answer is still
*this* caller's view: rendered from the text in hand, marked with the handle in
hand, and honest in the footer about not having been asked for just now.
"""

from __future__ import annotations

import pytest

from sift import answers, capture, distill, store, view
from sift import digest as d
from test_background import _Bridge
from test_distill import _Judge

LOG = "one\ntwo\nthree\nfour\nfive\n"


@pytest.fixture(autouse=True)
def _remembering(monkeypatch):
    monkeypatch.setenv("SIFT_CACHE", "1")


@pytest.fixture
def kayit(tmp_path):
    path = tmp_path / "ci.log"
    path.write_text(LOG, encoding="utf-8")
    return path


def test_the_second_ask_is_not_asked(kayit):
    judge = _Judge("2")

    first = d.digest(kayit, judge)
    second = d.digest(kayit, judge)

    assert len(judge.seen) == 1, "the model was asked about the same bytes twice"
    assert first is not None and second is not None
    assert (first.asks, second.asks) == (1, 0)


def test_what_comes_back_is_the_same_text(kayit):
    """The other half of the saving, and the one a client feels. A tool that
    answered a repeated question with a slightly different string would be a
    source of new strings for the transcript it exists to keep small."""
    judge = _Judge("2")

    first = d.digest(kayit, judge)
    second = d.digest(kayit, judge)

    assert first is not None and second is not None
    assert first.text == second.text


def test_a_remembered_answer_is_rendered_against_the_text_in_hand():
    """Why the numbers are kept and never the view.

    Two captures of the same output are the same bytes and the same question, so
    the second is answered from the first. But every gap marker names a handle,
    and handing back the first one's text would send a reader of the second to
    somebody else's capture.
    """
    said = "python3 -c \"print('\\n'.join(str(n) for n in range(60)))\""
    one = capture.run([said], shell=True)
    two = capture.run([said], shell=True)
    assert one.handle != two.handle

    first = distill.distill(one, _Bridge("3"))
    second = distill.distill(two, _Bridge("3"))

    assert first is not None and second is not None
    assert second.asks == 0, "the second capture was judged again"
    assert one.handle in first.text
    assert two.handle in second.text
    assert one.handle not in second.text


def test_a_remembered_view_says_it_was_remembered(kayit):
    """A reader watching a tool spend requests deserves to know which views cost
    one. Naming the model without saying that is implying it was reached."""
    judge = _Judge("2")
    d.digest(kayit, judge)

    built = d.digest(kayit, judge)

    assert built is not None
    assert view.chose(built) == "test-model (remembered)"


def test_a_different_question_about_the_same_text_is_a_different_question(kayit):
    """`outline` and `digest` read the same bytes and ask opposite things. An
    answer to one is not an answer to the other, so the key holds the question."""
    from sift import outline

    judge = _Judge("2")

    d.digest(kayit, judge)
    outline.outline(kayit, judge)

    assert len(judge.seen) == 2


def test_a_changed_file_is_a_different_question(kayit):
    judge = _Judge("2", "3")

    d.digest(kayit, judge)
    kayit.write_text(LOG + "six\n", encoding="utf-8")
    d.digest(kayit, judge)

    assert len(judge.seen) == 2


def test_a_different_ceiling_is_a_different_question(kayit):
    judge = _Judge("2")

    d.digest(kayit, judge, budget=10)
    d.digest(kayit, judge, budget=3)

    assert len(judge.seen) == 2


def test_keep_is_applied_to_a_remembered_answer_and_not_kept_in_it(kayit):
    """`keep` is an instruction that belongs to the call, not an answer that
    belongs to the text. Remembering it would hand the next caller lines they
    never asked for; failing to apply it on a hit would drop a line they did."""
    judge = _Judge("2")

    d.digest(kayit, judge)
    with_pattern = d.digest(kayit, judge, keep="five")

    assert with_pattern is not None
    assert with_pattern.asks == 0
    assert "five" in with_pattern.text

    plain = d.digest(kayit, judge)
    assert plain is not None
    assert "five" not in plain.text


def test_nothing_is_remembered_when_it_is_turned_off(kayit, monkeypatch):
    monkeypatch.setenv("SIFT_CACHE", "0")
    judge = _Judge("2")

    d.digest(kayit, judge)
    d.digest(kayit, judge)

    assert len(judge.seen) == 2
    assert not answers.kept_dir().exists()


def test_an_unreadable_note_is_a_question_nobody_asked(kayit):
    """A cache that raised would be a cache that can break a run, and what it
    holds can always be bought again."""
    judge = _Judge("2", "3")
    d.digest(kayit, judge)

    for found in answers.kept_dir().iterdir():
        found.write_text("{ this is not json", encoding="utf-8")

    built = d.digest(kayit, judge)

    assert built is not None
    assert len(judge.seen) == 2


def test_gc_drops_answers_nothing_has_asked_for(kayit):
    judge = _Judge("2")
    d.digest(kayit, judge)
    kept = list(answers.kept_dir().iterdir())
    assert len(kept) == 1

    import os

    old = store.now() - 40 * 86_400.0
    os.utime(kept[0], (old, old))

    forgotten, freed = answers.forget(30 * 86_400.0)

    assert forgotten == 1
    assert freed > 0
    assert not kept[0].exists()


def test_an_answer_that_is_still_being_used_is_not_old(kayit):
    """Swept by when it was last wanted, not by when it was written. An answer
    about a log somebody reads every morning is not old."""
    judge = _Judge("2")
    d.digest(kayit, judge)
    kept = list(answers.kept_dir().iterdir())

    import os

    old = store.now() - 40 * 86_400.0
    os.utime(kept[0], (old, old))

    d.digest(kayit, judge)  # read it: that is what makes it recent

    assert answers.forget(30 * 86_400.0) == (0, 0)
    assert kept[0].exists()
