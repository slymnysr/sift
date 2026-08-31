"""Faz 6 -- what a file declares, chosen without knowing what language it is in.

The test that carries this phase is the one that writes the same bytes under
five different names and demands the same outline back from all of them. The
design this replaced had a thousand lines of language table keyed on exactly
those names; if any of it had survived the rewrite, that test would fail.

The rest guard the promise `distill` already makes and `outline` now shares:
nothing the model writes can reach a view, and every line shown comes from the
file byte for byte.
"""

from __future__ import annotations

import re
import sys

import pytest

from sift import cli
from sift import distill as d
from sift import lines as text_lines
from sift import outline as o
from sift.capture import run
from sift.model import Answer
from sift.peek import peek

MARKER = re.compile(r"^─ ([\d,]+) lines? not shown · sift peek (\S+) for any of them ─$")


@pytest.fixture(autouse=True)
def _offline(tmp_path, monkeypatch):
    """No key, no stored key, and a store of its own."""
    monkeypatch.setenv("SIFT_HOME", str(tmp_path / "sift"))
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("SIFT_API_KEY", "NVIDIA_API_KEY", "SIFT_MODELS", "SIFT_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


class _Judge:
    """A model that answers however the test tells it to, and remembers what it saw."""

    def __init__(self, *replies, model: str = "test-model") -> None:
        self.replies = list(replies) or [""]
        self.model = model
        self.seen: list[tuple[str, str]] = []

    def ask(self, system: str, user: str, *, max_tokens: int = 1024):
        self.seen.append((system, user))
        reply = self.replies[min(len(self.seen) - 1, len(self.replies) - 1)]
        if reply is None:
            return None
        return Answer(text=reply, model=self.model, tries=1)

    @property
    def prompt(self) -> str:
        return self.seen[-1][1]


def _shown(view) -> list[str]:
    return [line for line in text_lines.of(view.text) if not MARKER.match(line)]


def _write(path, text: str):
    path.write_bytes(text.encode("utf-8"))
    return path


# -- the phase's own claim --------------------------------------------------


def test_the_name_of_a_file_plays_no_part_in_its_outline(tmp_path):
    """Same bytes, five names, one outline -- and one prompt.

    A suffix table cannot survive this. Neither can a filename table: `Makefile`
    was one of the entries the old design kept by name, and here it is asked
    about in exactly the words a file called `d` is asked about.
    """
    body = "def bir():\n    return 1\n\ndef iki():\n    return 2\n"
    prompts = set()
    for name in ("a.py", "b.rs", "c.qqzz", "Makefile", "d"):
        judge = _Judge("1, 4")
        view = o.outline(_write(tmp_path / name, body), judge)
        assert view is not None
        assert _shown(view) == ["def bir():", "def iki():"]
        prompts.add(judge.prompt)
    assert len(prompts) == 1


def test_a_language_no_table_could_have_had_is_outlined_like_any_other(tmp_path):
    """Invented syntax, invented extension, and the machinery does not notice.

    This is what the old design could not do without an eighty-fifth entry. It
    is also the honest test of the claim, because nobody -- including whoever
    wrote this test -- can look up what `kur` means.
    """
    body = "kur Deney <ol>\n  say 3\n<son>\nkur Bitir <ol>\n  say 0\n<son>\n"
    judge = _Judge("1, 4")
    view = o.outline(_write(tmp_path / "deney.qqzz", body), judge)
    assert _shown(view) == ["kur Deney <ol>", "kur Bitir <ol>"]


# -- nothing the model writes gets in ---------------------------------------


def test_nothing_the_model_writes_reaches_the_outline(tmp_path):
    body = "func Bir() {}\nfunc Iki() {}\n"
    reply = "The file declares Bir and Iki.\nfunc Uc() {}\nLines: 1, 2"
    view = o.outline(_write(tmp_path / "kaynak.go", body), _Judge(reply))
    assert "Uc" not in view.text
    assert "declares" not in view.text
    assert _shown(view) == ["func Bir() {}", "func Iki() {}"]


def test_the_prompt_shows_the_model_the_file_and_nothing_else(tmp_path):
    body = ["def bir():", "    return 1", "def iki():", "    return 2"]
    judge = _Judge("1, 3")
    o.outline(_write(tmp_path / "x.py", "\n".join(body) + "\n"), judge)
    assert text_lines.of(judge.prompt) == [
        f"{n}| {line}" for n, line in enumerate(body, 1)
    ]
    # The question asked is the one this module wrote, not the one `distill`
    # asks about a command's output. Two questions, one machine underneath.
    assert judge.seen[-1][0] == o.QUESTION


def test_the_question_asks_for_numbers_in_the_one_shared_way(tmp_path):
    """One parser reads every answer, so one sentence describes every answer."""
    assert o.QUESTION.endswith(d.ANSWER_FORMAT)
    assert d.QUESTION.endswith(d.ANSWER_FORMAT)
    assert o.QUESTION.count("Answer with line numbers only") == 1
    assert str(o.BUDGET) in o.QUESTION


# -- the file is read the way the rest of the tool reads bytes ---------------


def test_a_file_read_as_text_would_not_be_the_same_file(tmp_path):
    """`read_text` would grow this file a line that was never written."""
    path = tmp_path / "ilerleme.log"
    path.write_bytes(b"bir\n[1/2]\r[2/2]\niki\n")
    assert o.read(path) == ["bir", "[1/2]\r[2/2]", "iki"]
    assert len(path.read_text().splitlines()) == 4


def test_an_empty_file_has_an_empty_outline_and_nobody_is_asked(tmp_path):
    judge = _Judge("1, 2")
    view = o.outline(_write(tmp_path / "bos.py", ""), judge)
    assert view is not None
    assert (view.text, view.kept, view.total) == ("", 0, 0)
    assert judge.seen == []


def test_an_over_long_answer_is_shown_whole_rather_than_quietly_trimmed(tmp_path):
    """The budget is asked for, not enforced -- and a long outline says so.

    Cutting the answer back would mean ranking declarations without reading the
    language. `kept` out of `total` is the honest alternative: the reader can
    see that the outline came back long.
    """
    count = o.BUDGET * 3
    body = "\n".join(f"def f{n}(): pass" for n in range(count)) + "\n"
    view = o.outline(_write(tmp_path / "buyuk.py", body), _Judge(f"1-{count}"))
    assert (view.kept, view.total) == (count, count)


# -- the way back -----------------------------------------------------------


def test_the_gap_marker_names_the_path_as_the_way_back(tmp_path):
    body = "".join(f"satir {n}\n" for n in range(1, 21))
    path = _write(tmp_path / "yol.py", body)
    view = o.outline(path, _Judge("1"))
    found = [MARKER.match(line) for line in text_lines.of(view.text)]
    marks = [m for m in found if m]
    assert marks and all(m.group(2) == str(path) for m in marks)


def test_peek_takes_the_path_the_outline_handed_out(tmp_path):
    body = "".join(f"satir {n}\n" for n in range(1, 21))
    path = _write(tmp_path / "yol.py", body)
    view = o.outline(path, _Judge("1"))
    found = peek(view.handle, 4, 6)
    assert found.text == "satir 4\nsatir 5\nsatir 6"
    assert found.total_lines == 20


def test_a_capture_is_not_shadowed_by_a_file_that_shares_its_name(tmp_path, monkeypatch):
    """The store is asked first, so a decoy in the working directory cannot answer."""
    capture = run([sys.executable, "-c", "print('yakalama')"])
    (tmp_path / capture.handle).write_bytes(b"tuzak\n")
    monkeypatch.chdir(tmp_path)
    assert peek(capture.handle).text == "yakalama"


def test_a_handle_that_is_neither_a_capture_nor_a_file_is_refused():
    with pytest.raises(FileNotFoundError):
        peek("boyle-bir-sey-yok")


# -- without a model --------------------------------------------------------


def test_without_a_model_the_ends_are_shown_and_the_middle_is_counted(tmp_path):
    body = "".join(f"satir {n}\n" for n in range(1, 201))
    view = o.ends_of(_write(tmp_path / "uzun.py", body))
    assert view.model is None
    assert (view.kept, view.total) == (50, 200)
    assert "150 lines not shown" in view.text


# -- the command line -------------------------------------------------------


def test_the_command_line_outlines_a_file_with_no_model_at_all(tmp_path, capsys):
    path = _write(tmp_path / "kaynak.py", "def bir():\n    return 1\n")
    assert cli.main(["outline", str(path)]) == 0
    said = capsys.readouterr()
    assert "def bir():" in said.out
    assert "no model" in said.err
    assert str(path) in said.err


def test_outlining_a_file_that_is_not_there_is_reported_not_raised(tmp_path, capsys):
    assert cli.main(["outline", str(tmp_path / "yok.py")]) == 1
    assert "sift:" in capsys.readouterr().err


def test_outline_without_a_path_says_so_and_shows_the_usage(tmp_path, capsys):
    assert cli.main(["outline"]) == 2
    assert "sift outline" in capsys.readouterr().err
