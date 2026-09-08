"""Faz 13 -- a file somebody else produced.

The same engine, a third question. What is defended here is that it really is a
third one: asked of a log, "what does this declare" returns nothing worth
having, and a caller who reached for `digest` said which of the two they meant.
"""

from __future__ import annotations

import pytest

from sift import cli, view
from sift import digest as d
from test_distill import _Judge

LOG = """\
2026-09-02T04:11:07 Building 214 targets
2026-09-02T04:11:08 [1/214] compiling parser.rs
2026-09-02T04:12:44 ERROR: //src/parser:parse_test failed in 4.1s
2026-09-02T04:12:45 FAILED: 1 of 214 targets
"""


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFT_HOME", str(tmp_path / "sift"))
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("SIFT_API_KEY", "NVIDIA_API_KEY", "SIFT_MODELS", "SIFT_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def kayit(tmp_path):
    path = tmp_path / "ci.log"
    path.write_text(LOG, encoding="utf-8")
    return path


def test_a_digest_asks_what_happened_and_not_what_is_declared(kayit):
    """The whole reason this is a third command and not a flag on `outline`.

    One question is about a file that says what it contains; the other is about
    a file that says what took place. Asking either of them the other's question
    gets a confident answer to something nobody wanted to know.
    """
    judge = _Judge("3")
    d.digest(kayit, judge)

    asked = judge.seen[-1][0]
    assert "log" in asked or "transcript" in asked
    assert "declare" not in asked


def test_the_lines_of_a_digest_are_the_file_s_own(kayit):
    judge = _Judge("3")

    got = d.digest(kayit, judge)

    assert "ERROR: //src/parser:parse_test failed in 4.1s" in got.text
    assert kayit.read_text(encoding="utf-8") == LOG, "the file was written to"


def test_a_digest_is_handled_by_its_path_so_peek_takes_it_back(kayit):
    judge = _Judge("3")

    got = d.digest(kayit, judge)

    assert got.handle == str(kayit)
    assert str(kayit) in got.text, "the gap marker must name the way back"


def test_a_caller_may_set_the_ceiling_and_name_what_to_keep(kayit):
    judge = _Judge("1")

    got = d.digest(kayit, judge, budget=1, keep="FAILED")

    assert "FAILED: 1 of 214 targets" in got.text
    assert "Building 214 targets" in got.text


def test_a_file_that_cannot_be_read_is_a_sentence_and_not_a_crash(capsys, tmp_path):
    assert cli.main(["digest", str(tmp_path / "yokboyle.log")]) == 1
    assert "sift: " in capsys.readouterr().err


def test_without_a_model_a_digest_still_shows_the_file(capsys, kayit):
    """The third rule, for the third question.

    No key here, so nothing was asked. The ends of the file are worse than a
    chosen view and they are not wrong, and the footer says which one this is.
    """
    assert cli.main(["digest", str(kayit)]) == 0

    said = capsys.readouterr()
    assert "Building 214 targets" in said.out
    assert "no model" in said.err


def test_a_bug_in_the_digester_costs_the_view_and_nothing_else(capsys, kayit, monkeypatch):
    def explode(path, bridge=None, budget=None, keep=None):
        raise RuntimeError("damitici kirildi")

    monkeypatch.setattr(view, "digest", explode)

    assert cli.main(["digest", str(kayit)]) == 0
    said = capsys.readouterr()
    assert "Building 214 targets" in said.out
    assert "RuntimeError" in said.err
