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
    def explode(path, bridge=None, budget=None, keep=None, name=None):
        raise RuntimeError("damitici kirildi")

    monkeypatch.setattr(view, "digest", explode)

    assert cli.main(["digest", str(kayit)]) == 0
    said = capsys.readouterr()
    assert "Building 214 targets" in said.out
    assert "RuntimeError" in said.err


# -- the other way somebody else's output arrives -----------------------------


def _piped(monkeypatch, text: str) -> None:
    """Put `text` where the shell would have put a pipe."""
    import io

    class _Stdin:
        buffer = io.BytesIO(text.encode("utf-8"))

    monkeypatch.setattr(cli.sys, "stdin", _Stdin)


def test_a_pipe_is_read_and_kept(capsys, monkeypatch):
    """`journalctl | sift digest -` is the same question asked about a stream.

    What arrives has no path anybody can type again, so it is kept as a capture
    and the gap marker names the handle instead. The second rule is the whole
    reason for that: a view that left lines out and pointed at a scratch file
    would be pointing at nothing by the time somebody read it.
    """
    # Long enough that even the view nobody was asked about leaves lines out --
    # otherwise there is no gap, and the marker this test is about never gets
    # printed. The suite runs with no model on purpose.
    _piped(monkeypatch, "".join(f"satir {n}\n" for n in range(200)))

    assert cli.main(["digest", "-"]) == 0

    said = capsys.readouterr()
    handle = said.err.split()[1]
    assert len(handle) == 8, said.err
    assert f"sift peek {handle}" in said.out, "bosluk isareti tutamaci adlandirmali"


def test_what_was_piped_comes_back_byte_for_byte(capsys, monkeypatch):
    """And the loop closes: the handle in the marker is one `peek` takes."""
    _piped(monkeypatch, "bir\niki\nHATA: uc\ndort\n")
    cli.main(["digest", "-"])
    handle = capsys.readouterr().err.split()[1]

    assert cli.main(["peek", handle]) == 0

    assert capsys.readouterr().out == "bir\niki\nHATA: uc\ndort\n"


def test_a_stream_longer_than_one_block_arrives_whole(capsys, monkeypatch):
    """A pipe has no length, and the one it has is not the size of a read.

    This is the case the feature exists for -- a log too big to paste is the
    reason somebody reaches for a pipe at all -- and it is the case a test with
    four lines in it silently never covers. The mutation battery found that:
    reading a single block passed every test here until this one existed.
    """
    from sift import capture

    lines = [f"satir {n}\n" for n in range(20_000)]
    text = "".join(lines)
    assert len(text.encode()) > capture._READ_CHUNK, "test tek bloktan buyuk olmali"
    _piped(monkeypatch, text)

    cli.main(["digest", "-"])
    handle = capsys.readouterr().err.split()[1]
    cli.main(["peek", handle])

    assert capsys.readouterr().out == text


def test_an_outline_can_be_piped_too(capsys, monkeypatch):
    """The same word, on the other question, because they must not drift."""
    _piped(monkeypatch, "def bir():\n    pass\n\ndef iki():\n    pass\n")

    assert cli.main(["outline", "-"]) == 0

    said = capsys.readouterr()
    assert len(said.err.split()[1]) == 8
