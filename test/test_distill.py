"""Faz 3 -- the model chooses lines, and the lines come from the file.

The tests that matter most here are the ones that try to get text the model
wrote into the view. If any of them ever succeeds, the tool has become a
summariser and its central promise is gone.
"""

from __future__ import annotations

import re
import sys
import threading
from pathlib import Path

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


def text_lines_of(capture):
    """The lines of a capture, the way `distill` counts them."""
    from sift import lines as text_lines

    return text_lines.of(capture.text())


def _lines(count: int):
    return _python(f"for n in range(1, {count + 1}): print(f'satir {{n}}')")


class _Judge:
    """A model that answers however the test tells it to, and remembers what it saw.

    Replies are used in order; the last one keeps being used after that, so a
    test that does not care how many times it is asked does not have to count.

    The pieces of one capture are asked about at the same time, so `ask` is
    called from several threads. Recording the question and picking the reply
    for it happen together under a lock, or two threads counting the same length
    would be handed the same reply. A reply that is a function is called outside
    the lock, because a test that proves the asking overlaps does it by making
    one call wait for another.
    """

    def __init__(
        self,
        *replies,
        model: str = "test-model",
        tokens: int = 0,
        carried: int = 0,
    ) -> None:
        self.replies = list(replies) or [""]
        self.model = model
        # What each answer claims to have cost. Zero by default, which is what an
        # endpoint that did not say costs, and what every test that is not about
        # counting should see.
        self.tokens = tokens
        # And what each answer claims the question weighed. Zero for the same
        # reason: an endpoint that did not say did not say.
        self.carried = carried
        self.seen: list[tuple[str, str]] = []
        self._turn = threading.Lock()

    def ask(self, system: str, user: str, *, max_tokens: int = 1024):
        with self._turn:
            self.seen.append((system, user))
            reply = self.replies[min(len(self.seen) - 1, len(self.replies) - 1)]
        if callable(reply):
            reply = reply(user)
        if reply is None:
            return None
        return Answer(
            text=reply,
            model=self.model,
            tries=1,
            tokens=self.tokens,
            carried=self.carried,
        )

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


def test_the_readme_shows_the_marker_this_code_actually_writes():
    """Documentation that cannot drift: the example in the README is generated here.

    A format string and a README are two places to say the same thing, and one
    of them is never run. This makes the unread one fail out loud.
    """
    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text("utf-8")
    assert d.gap(3_914, "9f2c41ab") in readme


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

    # Sorted by the number each piece starts at, because the pieces are asked
    # about at the same time and no longer arrive in the order they were cut.
    in_order = sorted(judge.seen, key=lambda pair: int(pair[1].partition("|")[0]))
    firsts = [prompt.splitlines()[0].partition("| ")[2] for _, prompt in in_order]
    assert _shown(view) == firsts


# -- Faz 8: what a view is allowed to cost ----------------------------------


def _asked_about(prompt: str) -> list[int]:
    """The line numbers one ask was shown, read back out of the prompt."""
    return [int(line.partition("| ")[0]) for line in prompt.splitlines()]


def test_the_budget_is_divided_between_asks_and_not_repeated_to_each():
    """The bug this phase exists for, in one assertion.

    A capture split into five asks used to be five times told to keep a hundred
    lines. Every ask obeyed, and the view came back five hundred lines long --
    which is how a tool that promises to cost a page ends up costing a chapter
    on exactly the output nobody could read anyway. What each ask is told now
    has to be a share of the whole, or the arithmetic is back.
    """
    judge = _Judge("1")
    d.distill(_lines(20_000), judge)

    asks = len(judge.seen)
    assert asks > 1, "not enough pieces to divide anything between"
    each = d.BUDGET // asks
    assert each < d.BUDGET
    for system, _ in judge.seen:
        assert f"about {each} lines" in system


def test_a_capture_that_fits_in_one_ask_is_told_the_whole_budget():
    judge = _Judge("1")
    d.distill(_lines(5), judge)

    assert len(judge.seen) == 1
    assert f"about {d.BUDGET} lines" in judge.seen[0][0]


def test_a_share_never_falls_to_nothing():
    """More asks than lines to go round still asks each for one, never for none."""
    assert "about 1 line." in d.ceiling(3, 1000)
    assert "about 2 lines." in d.ceiling(4, 2)


def test_an_over_long_answer_is_handed_back_rather_than_cut():
    """Too many lines is a question for the model, not arithmetic for the code.

    The first answer keeps everything. The second is asked about that answer and
    keeps a tenth of it. Nothing here chose which tenth, and nothing here could
    have: dropping the short runs loses a lone failure, dropping the long ones
    loses a stack trace, and dropping from the middle is a coin toss.
    """
    judge = _Judge("1-400", "1-40")
    view = d.distill(_lines(400), judge)

    assert view.kept == 40
    assert view.asks == 2
    assert _shown(view) == [f"satir {n}" for n in range(1, 41)]


def test_the_second_pass_asks_a_different_question_from_the_first():
    """Asked the same question twice, a model gives the same answer -- correctly.

    A shortlist of lines that all matter is a right answer to "which lines
    matter". Measured, that came back four asks and 359 lines against a budget
    of 120. The round has to say what the list already is.
    """
    judge = _Judge("1-400", "1-40")
    d.distill(_lines(400), judge)

    first, second = (system for system, _ in judge.seen)
    assert d.NARROWING not in first
    assert d.NARROWING in second
    assert second.startswith(d.QUESTION)


def test_the_second_pass_is_shown_the_lines_it_chose_and_no_others():
    """The shortlist is the first answer, still carrying the capture's numbers.

    Renumbering it from one would make every answer about the shortlist point at
    the top of the capture -- confidently, and wrongly.
    """
    judge = _Judge("200-400", "200-210")
    view = d.distill(_lines(400), judge)

    assert _asked_about(judge.seen[1][1]) == list(range(200, 401))
    assert _shown(view) == [f"satir {n}" for n in range(200, 211)]
    assert view.kept == 11


def test_narrowing_can_only_drop_lines_and_never_add_one():
    """A number from outside the shortlist is dropped rather than admitted.

    A second pass that could widen would be a second chance to show a line the
    first pass rejected, granted by a model that was never shown it.
    """
    judge = _Judge("1-200", "1-5, 380-400")
    view = d.distill(_lines(400), judge)

    assert _shown(view) == [f"satir {n}" for n in range(1, 6)]
    assert view.kept == 5


def test_a_round_that_answers_nothing_leaves_the_first_answer_standing():
    """An unanswered question is not a decision to show nothing."""
    view = d.distill(_lines(400), _Judge("1-300", None))

    assert view.kept == 300
    assert view.asks == 2


def test_narrowing_stops_when_it_stops_shortening_anything():
    """A model that will not narrow is asked once more, not three times more."""
    view = d.distill(_lines(400), _Judge("1-400"))

    assert view.kept == 400
    assert view.asks == 2, "one first pass, one round that changed nothing"


def test_a_view_still_over_budget_after_three_rounds_comes_back_long():
    """The ceiling is a request, and the last word about length is the truth.

    Three rounds of narrowing, each one shorter and none of them short enough.
    What comes back is 200 lines against a budget of 120, and it says so --
    which is worth more than 120 lines nobody chose.
    """
    judge = _Judge("1-1000", "1-800", "1-400", "1-200")
    view = d.distill(_lines(1000), judge)

    assert view.asks == 1 + d.NARROW_ROUNDS
    assert view.kept == 200
    assert view.kept > d.BUDGET


def test_a_shortlist_too_long_for_one_ask_is_split_the_way_a_capture_is():
    """The second pass reuses the first pass's splitting, numbering and all."""
    judge = _Judge("1-20000")
    view = d.distill(_lines(20_000), judge)

    half = len(judge.seen) // 2
    assert half > 1, "not enough pieces to prove the shortlist was split at all"
    assert view.kept == 20_000, "this judge narrows nothing"
    # Compared as sets: the first pass asks its pieces at the same time and the
    # second pass asks them one after another, so the same pieces arrive in two
    # different orders. What is being checked is that they are the same pieces.
    assert sorted(p for _, p in judge.seen[:half]) == sorted(
        p for _, p in judge.seen[half:]
    )
    assert all(len(prompt) <= d.CHARS_PER_ASK for _, prompt in judge.seen)


def test_the_pieces_of_a_capture_are_asked_about_at_the_same_time():
    """Seven questions asked one after another is seven waits.

    Proved by making the answers depend on each other: a reply is only given
    once two calls have met at the barrier. Asked one at a time the first call
    waits alone until the barrier gives up, and nothing ever meets.
    """
    met = threading.Barrier(2, timeout=5)
    overlapped = threading.Event()

    def answer(_prompt: str) -> str:
        try:
            met.wait()
            overlapped.set()
        except threading.BrokenBarrierError:
            pass
        return "1-1"

    judge = _Judge(answer)
    view = d.distill(_lines(20_000), judge)

    assert view.asks > 1, "one piece proves nothing about asking two at once"
    assert overlapped.is_set(), "the pieces were asked about one after another"


def test_a_question_that_came_back_with_nothing_is_counted():
    """A view built from one answer out of many is not a short view."""
    answers = iter(["1-3", None, None])
    judge = _Judge(lambda _prompt: next(answers, None))

    view = d.distill(_lines(20_000), judge)

    assert view.asks > 1
    assert view.unanswered == view.asks - 1
    assert view.kept == 3


def test_a_view_that_got_every_answer_counts_no_silence():
    judge = _Judge("1-5")
    view = d.distill(_lines(400), judge)

    assert view.unanswered == 0


def test_asking_one_piece_at_a_time_gives_the_same_answer(monkeypatch):
    """Parallel is a claim about waiting, not about what comes back."""
    monkeypatch.setenv("SIFT_WORKERS", "1")
    serial = d.distill(_lines(20_000), _Judge(lambda p: p.split("|", 1)[0]))
    monkeypatch.setenv("SIFT_WORKERS", "6")
    parallel = d.distill(_lines(20_000), _Judge(lambda p: p.split("|", 1)[0]))

    # Compared line by line rather than as whole text: every run gets its own
    # handle, and the handle is printed in the gap markers.
    assert _shown(serial) == _shown(parallel)
    assert serial.kept == parallel.kept
    assert _hidden(serial) == _hidden(parallel)


def test_how_many_pieces_at_once_can_be_set_and_never_falls_below_one(monkeypatch):
    monkeypatch.delenv("SIFT_WORKERS", raising=False)
    assert d.workers() == d.WORKERS
    monkeypatch.setenv("SIFT_WORKERS", "3")
    assert d.workers() == 3
    monkeypatch.setenv("SIFT_WORKERS", "0")
    assert d.workers() == 1
    monkeypatch.setenv("SIFT_WORKERS", "hepsi")
    assert d.workers() == d.WORKERS


def test_a_caller_may_ask_for_no_ceiling_at_all():
    """`budget=None` says nothing about length and hands nothing back."""
    body = [f"satir {n}" for n in range(1, 401)]
    judge = _Judge("1-400")
    view = d.select(body, d.QUESTION, "elde", judge, budget=None)

    assert view.kept == 400
    assert view.asks == 1
    assert judge.seen[0][0] == d.QUESTION + d.ANSWER_FORMAT

# -- Faz 12: the caller's own say --------------------------------------------


def test_a_line_the_caller_asked_for_is_shown_though_the_model_passed_it_over():
    """`keep` is the one pattern in the judging path, and it is not this tool's.

    A rule invented here about what output looks like would be a guess about
    languages it half knows. A pattern the caller typed is a request: they know
    what they are looking for, and the only job left is to not lose it.
    """
    judge = _Judge("1")
    got = _python("print('bir'); print('KEYWORD'); print('uc')")

    view = d.select(text_lines_of(got), "soru", got.handle, judge, keep="KEYWORD")

    assert "KEYWORD" in view.text
    assert "bir" in view.text  # what the model chose is still there


def test_what_the_caller_asked_for_survives_the_budget():
    """A ceiling is this tool's opinion; `keep` is an instruction.

    An instruction that a default silently overrode would be worse than no
    instruction at all, so the keeping happens after the narrowing rather than
    inside it.
    """
    judge = _Judge("1")
    got = _python("for n in range(6): print('TUT' if n % 2 else f'satir {n}')")

    view = d.select(text_lines_of(got), "soru", got.handle, judge, budget=1, keep="TUT")

    assert view.text.count("TUT") == 3
    assert view.kept > 1, "the budget was allowed to eat the request"


def test_a_pattern_that_matched_is_an_answer_even_when_nobody_replied():
    judge = _Judge(None)
    got = _python("print('bir'); print('TUT')")

    view = d.select(text_lines_of(got), "soru", got.handle, judge, keep="TUT")

    assert view is not None
    assert "TUT" in view.text
    assert view.model is None, "no model answered, and the view must not claim one"


def test_a_pattern_that_will_not_compile_is_searched_for_as_text():
    """Someone who typed `main()` meant those characters.

    Answering a mistyped group with silence would drop the request without ever
    saying so, which is the one outcome a caller cannot detect.
    """
    judge = _Judge("")
    got = _python("print('void main() {')")

    view = d.select(text_lines_of(got), "soru", got.handle, judge, keep="main()")

    assert "main()" in view.text


def test_keeping_a_line_does_not_move_any_number():
    judge = _Judge("2")
    got = _python("print('bir'); print('iki'); print('TUT')")

    view = d.select(text_lines_of(got), "soru", got.handle, judge, keep="TUT")

    assert _shown(view) == ["iki", "TUT"], "the order or the choice moved"
    assert view.total == 3
