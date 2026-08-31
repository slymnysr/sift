"""Faz 3 -- the model chooses lines, and the lines come from the file.

The tests that matter most here are the ones that try to get text the model
wrote into the view. If any of them ever succeeds, the tool has become a
summariser and its central promise is gone.
"""

from __future__ import annotations

import re
import sys

import pytest

from sift import distill as d
from sift.capture import run
from sift.model import Answer

MARKER = re.compile(r"^─ ([\d,]+) lines? not shown · sift peek (\S+) for any of them ─$")


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFT_HOME", str(tmp_path / "sift"))


def _python(code: str):
    return run([sys.executable, "-c", code])


def _lines(count: int):
    return _python(f"for n in range(1, {count + 1}): print(f'satir {{n}}')")


class _Judge:
    """A model that answers however the test tells it to, and remembers what it saw.

    Replies are used in order; the last one keeps being used after that, so a
    test that does not care how many times it is asked does not have to count.
    """

    def __init__(self, *replies, model: str = "test-model") -> None:
        self.replies = list(replies) or [""]
        self.model = model
        self.seen: list[tuple[str, str]] = []

    def ask(self, system: str, user: str, *, max_tokens: int = 1024):
        self.seen.append((system, user))
        reply = self.replies[min(len(self.seen) - 1, len(self.replies) - 1)]
        if callable(reply):
            reply = reply(user)
        if reply is None:
            return None
        return Answer(text=reply, model=self.model, tries=1)

    @property
    def prompt(self) -> str:
        return self.seen[-1][1]


def _shown(view) -> list[str]:
    return [line for line in view.text.splitlines() if not MARKER.match(line)]


def _hidden(view) -> int:
    total = 0
    for line in view.text.splitlines():
        found = MARKER.match(line)
        if found:
            total += int(found.group(1).replace(",", ""))
    return total


# -- what the model is asked ------------------------------------------------


def test_the_model_sees_numbered_lines_and_is_asked_for_numbers_alone():
    judge = _Judge("1")
    d.distill(_lines(3), judge)

    system, user = judge.seen[0]
    assert user.splitlines() == ["1| satir 1", "2| satir 2", "3| satir 3"]
    assert "numbers only" in system
    assert "do not quote any line" in system.lower()


def test_a_line_too_wide_to_judge_is_shortened_for_the_model_only():
    wide = "x" * 5000
    cap = _python(f"print('{wide}')")
    judge = _Judge("1")

    view = d.distill(cap, judge)

    asked = judge.prompt
    assert len(asked) < d.PROMPT_LINE_CAP + 50
    assert asked.endswith("…")
    assert view.text == wide  # what gets read is never the shortened one


# -- what comes back --------------------------------------------------------


def test_the_chosen_lines_are_the_capture_s_own_bytes():
    cap = _lines(5)
    view = d.distill(cap, _Judge("2, 4"))

    assert _shown(view) == ["satir 2", "satir 4"]
    assert view.kept == 2
    assert view.total == 5
    assert view.folded == 3
    assert view.model == "test-model"
    assert view.asks == 1


def test_text_the_model_writes_never_reaches_the_view():
    """The one guarantee the whole design exists for.

    A model that ignores the instruction and answers in prose still only
    contributes numbers. Its sentence is not quoted, not paraphrased, not
    shown -- the words it invented are simply never read.
    """
    cap = _lines(3)
    invented = "Segmentation fault in kernel module"
    view = d.distill(cap, _Judge(f"Line 2 is the problem: '{invented}'"))

    assert _shown(view) == ["satir 2"]
    assert invented not in view.text
    assert "Line" not in view.text


def test_a_line_number_the_capture_does_not_have_is_dropped():
    """Dropped, not merely unprintable.

    A number kept out of range shows nothing either way, so the view looks
    right while the count of what was chosen is a lie -- and the gaps are
    measured against that count.
    """
    view = d.distill(_lines(3), _Judge("2, 9999"))
    assert _shown(view) == ["satir 2"]
    assert view.kept == 1
    assert _hidden(view) == view.total - view.kept


def test_there_is_no_line_before_the_first_one():
    assert d.read_numbers("0, 2", 3) == {2}
    assert d.read_numbers("0-2", 3) == {1, 2}


def test_a_range_running_past_the_end_stops_at_the_end():
    view = d.distill(_lines(3), _Judge("1-9999"))
    assert _shown(view) == ["satir 1", "satir 2", "satir 3"]
    assert view.kept == 3


def test_a_range_given_backwards_is_still_a_range():
    view = d.distill(_lines(6), _Judge("5-3"))
    assert _shown(view) == ["satir 3", "satir 4", "satir 5"]


def test_a_range_written_with_a_typographic_dash_is_still_a_range():
    """A model writes "40\u201347" as readily as "40-47", and means the same lines.

    The dashes are written as escapes here for the same reason they are escapes
    in the pattern: three characters that look almost identical should not be
    told apart by eye.
    """
    assert d.read_numbers("2-3", 5) == {2, 3}
    assert d.read_numbers("2\u20133", 5) == {2, 3}
    assert d.read_numbers("2\u20143", 5) == {2, 3}


def test_the_same_line_named_twice_is_shown_once():
    view = d.distill(_lines(6), _Judge("2, 2-4, 3"))
    assert _shown(view) == ["satir 2", "satir 3", "satir 4"]
    assert view.kept == 3


def test_every_line_shown_is_a_line_of_the_capture_in_its_own_order():
    cap = _lines(40)
    original = cap.text().splitlines()
    view = d.distill(cap, _Judge("31, 3-5, 12, 40, 1"))

    rest = iter(original)
    assert all(line in rest for line in _shown(view))  # a subsequence, unaltered


# -- what is not shown ------------------------------------------------------


def test_a_gap_says_how_many_lines_and_how_to_reach_them():
    cap = _lines(10)
    view = d.distill(cap, _Judge("5"))

    first = view.text.splitlines()[0]
    found = MARKER.match(first)
    assert found, first
    assert found.group(1) == "4"
    assert found.group(2) == cap.handle


def test_a_single_hidden_line_is_counted_in_the_singular():
    view = d.distill(_lines(3), _Judge("1, 3"))
    assert "─ 1 line not shown" in view.text


def test_hidden_lines_are_written_with_thousands_marked():
    view = d.distill(_lines(4000), _Judge("4000"))
    assert "─ 3,999 lines not shown" in view.text


def test_the_gaps_account_for_every_line_that_is_not_shown():
    """A view that hid things without saying so would be asking to be trusted."""
    cap = _lines(60)
    view = d.distill(cap, _Judge("1, 8-11, 30, 55-58"))  # ends early: a tail to mark

    assert len(_shown(view)) == view.kept
    assert _hidden(view) == view.total - view.kept


def test_nothing_is_marked_when_nothing_is_hidden():
    view = d.distill(_lines(4), _Judge("1-4"))
    assert view.text == "satir 1\nsatir 2\nsatir 3\nsatir 4"


# -- when there is no judgement --------------------------------------------


def test_an_answer_without_numbers_is_no_answer():
    assert d.distill(_lines(3), _Judge("I could not tell which lines matter.")) is None


def test_a_model_that_cannot_be_reached_leaves_the_choice_to_the_caller():
    """Faz 4 supplies the fallback. Guessing here would hide that it is missing."""
    assert d.distill(_lines(3), _Judge(None)) is None


def test_an_empty_capture_is_not_worth_asking_about():
    view = d.distill(_python("pass"), _Judge("1"))
    assert view is not None
    assert view.text == ""
    assert view.total == 0
    assert view.asks == 0


# -- captures too long for one ask -----------------------------------------


def test_a_long_capture_is_asked_about_in_pieces():
    cap = _lines(8000)
    judge = _Judge(lambda prompt: prompt.split("|", 1)[0])

    view = d.distill(cap, judge)

    assert view.asks > 1
    assert len(judge.seen) == view.asks
    assert all(len(prompt) <= d.CHARS_PER_ASK for _, prompt in judge.seen)


def test_every_piece_keeps_the_numbering_of_the_whole_capture():
    """An answer about line 5,715 must mean line 5,715 of the capture.

    Numbering each piece from one would make every answer after the first point
    at the top of the file -- confidently, and wrongly. Checking only the second
    piece is not enough: a first and a last piece can both be right while every
    piece between them is off, so the capture here is long enough to have a
    middle, and every numbered line of every piece is checked against it.
    """
    cap = _lines(20_000)
    judge = _Judge(lambda prompt: prompt.split("|", 1)[0])

    view = d.distill(cap, judge)

    original = cap.text().splitlines()
    assert view.asks >= 3, "not enough pieces for a middle one"
    for _, prompt in judge.seen:
        for asked in prompt.splitlines():
            number, _, text = asked.partition("| ")
            assert original[int(number) - 1] == text

    firsts = [prompt.splitlines()[0].partition("| ")[2] for _, prompt in judge.seen]
    assert _shown(view) == firsts
