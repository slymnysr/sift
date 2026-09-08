"""What counts as a line, checked against what everything else counts."""

from __future__ import annotations

import shutil
import subprocess
import sys

import pytest

from sift import lines
from sift.capture import run
from sift.distill import numbered
from sift.peek import peek

# The characters Python breaks a line on that nothing else does. Written as
# escapes: half of them are invisible, and an invisible character in a test is a
# test nobody can review.
NOT_LINE_ENDINGS = ("\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029")


# A progress bar that redraws itself, written as the exact bytes it writes.
BAR = b"[1/3]\r[2/3]\r[3/3]\n"


def test_a_line_ends_at_a_newline_and_at_nothing_else():
    """Form feed, vertical tab, the separators, NEL, and the Unicode ones.

    Each of these turns up in real output -- NEL comes out of EBCDIC conversions,
    U+2028 out of tooling that pasted a string it read somewhere else. None of
    them is a line ending anywhere else, so none of them may add a line here.
    """
    for splitter in NOT_LINE_ENDINGS:
        text = f"bir{splitter}iki\n"
        assert lines.of(text) == [f"bir{splitter}iki"], repr(splitter)
        assert text.splitlines() != lines.of(text), (
            f"{splitter!r} has to split for this test to be testing anything"
        )


def test_a_carriage_return_before_a_newline_belongs_to_the_ending():
    assert lines.of("bir\r\niki\r\n") == ["bir", "iki"]
    assert lines.of("bir\r\n") == ["bir"]


def test_a_progress_bar_that_redraws_itself_is_one_line():
    """Nine hundred redraws are one line on a terminal, so they are one line here.

    Counting them separately would bury a build under a number counting up, and
    would let one second of work outvote everything else the command said.
    """
    bar = "".join(f"\r[{n}/900] indiriliyor" for n in range(1, 901))
    assert len(lines.of(bar + "\nbitti\n")) == 2


def test_a_trailing_newline_ends_the_last_line_rather_than_starting_another():
    assert lines.of("bir\niki\n") == ["bir", "iki"]
    assert lines.of("bir\niki") == ["bir", "iki"]
    assert lines.of("bir\niki\n\n") == ["bir", "iki", ""]


def test_nothing_written_is_no_lines_and_one_newline_is_one_empty_line():
    assert lines.of("") == []
    assert lines.of("\n") == [""]


def test_a_capture_keeps_the_carriage_returns_the_command_wrote():
    """Nothing between the pipe and the view may have an opinion on line endings.

    `store` reads captures as bytes. Read as text instead, universal newlines
    would rewrite every carriage return into a newline, and a progress bar that
    redrew itself a hundred times would arrive as a hundred lines that were
    never written -- each one numbered, and each one a number `peek` could not
    answer to.
    """
    capture = run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.stdout.buffer.write({BAR!r})",
        ]
    )
    said = capture.text()
    assert said.count("\r") == 2
    assert lines.of(said) == ["[1/3]\r[2/3]\r[3/3]"]


@pytest.mark.skipif(shutil.which("wc") is None, reason="wc yok")
def test_the_count_is_the_one_wc_would_give():
    """An oracle somebody else wrote, decades ago, in another language."""
    text = "bir\niki\x0cuc\r\ndort bes\n"
    said = subprocess.run(["wc", "-l"], input=text.encode(), capture_output=True)
    assert len(lines.of(text)) == int(said.stdout.split()[0])


def test_peek_and_the_prompt_agree_on_which_line_is_line_three():
    """The number the model is given is the number `peek` answers to.

    If these two ever disagreed, a view could point at a line and `peek` could
    show a different one -- which is the one thing this tool promises cannot
    happen.
    """
    # Written as bytes, and by this interpreter rather than by whatever `python3`
    # happens to mean here: the NEL below is exactly the character a console code
    # page cannot spell, which is the whole reason the sample has one.
    said = "bir\niki\x85uc\ndort\n"
    capture = run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.stdout.buffer.write({said.encode() !r})",
        ]
    )
    body = lines.of(capture.text())
    # Read back with the same rule it was written with: str.splitlines() would
    # split the prompt on the NEL inside line two and answer with the wrong line.
    assert lines.of(numbered(body))[2] == "3| dort"
    assert peek(capture.handle, 3, 3).text == "dort"
