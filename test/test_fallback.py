"""Faz 4 -- what gets shown when nobody could be asked.

The fallback is deliberately worse than a model. The thing it must never be is
wrong, so these tests are mostly about what it does *not* claim.
"""

from __future__ import annotations

import sys

import pytest

from sift import fallback as f
from sift.capture import run
from sift.distill import View
from test_distill import MARKER, _hidden, _shown


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFT_HOME", str(tmp_path / "sift"))


def _lines(count: int, code: int = 0):
    return run(
        [
            sys.executable,
            "-c",
            f"import sys\nfor n in range(1, {count + 1}): print(f'satir {{n}}')\n"
            f"sys.exit({code})",
        ]
    )


def test_a_capture_short_enough_to_read_is_shown_whole():
    view = f.fallback(_lines(f.HEAD + f.TAIL))
    assert view.kept == view.total
    assert not MARKER.search(view.text)


def test_a_long_capture_is_shown_from_both_ends():
    view = f.fallback(_lines(500))
    shown = _shown(view)
    assert shown[: f.HEAD] == [f"satir {n}" for n in range(1, f.HEAD + 1)]
    assert shown[-f.TAIL :] == [f"satir {n}" for n in range(500 - f.TAIL + 1, 501)]
    assert view.kept == f.HEAD + f.TAIL


def test_a_run_that_failed_gets_more_of_its_ending():
    """Where a failure explains itself, and how much of the explanation to keep."""
    worked = f.fallback(_lines(500))
    broke = f.fallback(_lines(500, code=1))
    assert broke.kept > worked.kept
    assert _shown(broke)[-1] == "satir 500"


def test_the_fallback_says_that_no_model_chose():
    """The reader can tell the two apart, and decide whether to read the rest."""
    view = f.fallback(_lines(500))
    assert view.model is None
    assert view.asks == 0


def test_nothing_is_shown_that_the_capture_does_not_contain():
    cap = _lines(500)
    original = set(cap.text().splitlines())
    assert all(line in original for line in _shown(f.fallback(cap)))


def test_the_gaps_account_for_every_line_that_is_not_shown():
    view = f.fallback(_lines(500))
    assert _hidden(view) == view.total - view.kept
    assert len(_shown(view)) == view.kept


def test_an_empty_capture_becomes_an_empty_view():
    view = f.fallback(run([sys.executable, "-c", "pass"]))
    assert view == View(view.handle, "", 0, 0, None, 0)


def test_the_ends_of_a_capture_shorter_than_the_ends_asked_for():
    assert f.ends(3, head=10, tail=40) == {1, 2, 3}
    assert f.ends(0, head=10, tail=40) == set()


def test_the_ends_never_overlap_into_a_claim_about_the_middle():
    chosen = f.ends(100, head=10, tail=40)
    assert chosen == set(range(1, 11)) | set(range(61, 101))
    assert 11 not in chosen
    assert 60 not in chosen
