"""Faz 4 -- the command line, and the promise that it cannot break your command.

Every test here runs with no API key and no network, which is the state the
third rule in the README is about. What the model would add is tested elsewhere;
what has to work without it is tested here.
"""

from __future__ import annotations

import sys

import pytest

from sift import capture, cli, store, view
from sift.distill import View

FAILING = "import sys; print('bir'); sys.exit(3)"


@pytest.fixture(autouse=True)
def _offline(tmp_path, monkeypatch):
    """No key, no stored key, and a store of its own."""
    monkeypatch.setenv("SIFT_HOME", str(tmp_path / "sift"))
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("SIFT_API_KEY", "NVIDIA_API_KEY", "SIFT_MODELS", "SIFT_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


def _run(code: str, *before: str) -> list[str]:
    return ["run", *before, "--", sys.executable, "-c", code]


# -- the shape of the interface --------------------------------------------


def test_no_arguments_explains_every_command(capsys):
    assert cli.main([]) == 0
    said = capsys.readouterr().out
    assert "sift run" in said
    assert "sift outline" in said
    assert "sift peek" in said
    assert "sift list" in said
    assert "sift stats" in said


def test_an_unknown_command_is_an_error_and_says_so_on_stderr(capsys):
    assert cli.main(["summarise"]) == 2
    assert "no such command" in capsys.readouterr().err


def test_run_without_a_command_is_an_error(capsys):
    assert cli.main(["run"]) == 2
    assert "needs a command" in capsys.readouterr().err


def test_flags_after_the_command_belong_to_the_command(capsys):
    """`sift run -- pytest --lf` must not have its own opinion about --lf."""
    code = "import sys; print(sys.argv[1:])"
    assert cli.main(["run", "--", sys.executable, "-c", code, "--help", "--timeout"]) == 0
    assert "['--help', '--timeout']" in capsys.readouterr().out


# -- nothing can break your command ----------------------------------------


def test_the_output_is_shown_even_though_no_model_could_be_asked(capsys):
    assert cli.main(_run("print('merhaba')")) == 0
    said = capsys.readouterr()
    assert said.out.strip() == "merhaba"
    assert "no model" in said.err


def test_the_command_s_own_exit_code_comes_back_out(capsys):
    """A script that failed when it ran `pytest` has to keep failing under sift."""
    assert cli.main(_run(FAILING)) == 3
    assert capsys.readouterr().out.strip() == "bir"


def test_a_command_that_cannot_be_run_says_so_the_way_a_shell_would(capsys):
    assert cli.main(["run", "--", "sift-no-such-program-anywhere"]) == cli.CANNOT_RUN
    assert "sift:" in capsys.readouterr().err


def test_a_command_that_runs_too_long_is_stopped_and_reported(capsys):
    assert cli.main(_run("import time; time.sleep(60)", "--timeout", "0.5")) == cli.TIMED_OUT
    assert "timed out" in capsys.readouterr().err


def test_a_broken_distiller_costs_the_view_and_nothing_else(capsys, monkeypatch):
    """The bug that must not reach the user: a crash in the part that is optional."""

    def explode(capture, bridge=None):
        raise RuntimeError("kirildi")

    monkeypatch.setattr(view, "distill", explode)

    assert cli.main(_run(FAILING)) == 3
    said = capsys.readouterr()
    assert said.out.strip() == "bir"
    assert "RuntimeError: kirildi" in said.err


def test_a_command_that_says_nothing_still_reports_its_ending(capsys):
    assert cli.main(_run("pass")) == 0
    said = capsys.readouterr()
    assert said.out == ""
    assert "exit 0" in said.err


def test_output_in_any_script_comes_back_unchanged(capsys):
    """A capture holds whatever the command wrote, in whatever language.

    Nothing between the pipe and the screen is allowed to have an opinion about
    which alphabets are printable.
    """
    said = "hata: dosya bulunamadi \u00b7 \u30a8\u30e9\u30fc \u00b7 \u062e\u0637\u0623"
    cli.main(_run(f"print({said!r})"))
    assert capsys.readouterr().out.strip() == said


def test_even_a_broken_fallback_costs_only_the_shortening(capsys, monkeypatch):
    """The floor: when everything that chooses lines fails, every line is shown.

    A bug in the part that shortens output must cost the shortening, not the
    output, and not the exit code the caller is about to act on.
    """

    def explode(capture, bridge=None):
        raise RuntimeError("damitici kirildi")

    def also_explode(capture):
        raise RuntimeError("yedek de kirildi")

    monkeypatch.setattr(view, "distill", explode)
    monkeypatch.setattr(view, "fallback", also_explode)

    assert cli.main(_run("import sys; print('bir'); print('iki'); sys.exit(3)")) == 3
    said = capsys.readouterr()
    assert said.out.splitlines() == ["bir", "iki"]
    assert "yedek de kirildi" in said.err
    assert "showing the capture unchanged" in said.err


# -- what the footer is for -------------------------------------------------


def test_the_view_goes_to_stdout_and_the_note_about_it_goes_to_stderr(capsys):
    """So that piping a view somewhere does not pipe sift's commentary with it."""
    cli.main(_run("print('yalniz bu')"))
    said = capsys.readouterr()
    assert said.out.strip() == "yalniz bu"
    assert said.out.count("sift ") == 0
    assert said.err.startswith("sift ")


def test_the_footer_names_the_model_when_there_was_one(capsys, monkeypatch):
    monkeypatch.setattr(
        view,
        "distill",
        lambda capture, bridge=None: View(capture.handle, "iki", 1, 9, "a-model", 1),
    )
    cli.main(_run("print('bir')"))
    said = capsys.readouterr()
    assert said.out.strip() == "iki"
    assert "a-model" in said.err
    assert "1/9 lines" in said.err


def test_the_footer_says_when_part_of_the_capture_was_never_looked_at(
    capsys, monkeypatch
):
    """Six answers missing out of seven is not the same as a short answer.

    Both read as a small number of lines out of a large one, in the same words.
    Without this the quieter of the two passes for the louder.
    """
    monkeypatch.setattr(
        view,
        "distill",
        lambda capture, bridge=None: View(
            capture.handle, "iki", 1, 9, "a-model", 7, unanswered=6
        ),
    )
    cli.main(_run("print('bir')"))

    assert "6 questions unanswered" in capsys.readouterr().err


def test_a_footer_with_every_answer_in_says_nothing_about_silence(capsys):
    cli.main(_run("print('bir')"))

    assert "unanswered" not in capsys.readouterr().err


def test_the_bill_records_the_questions_that_came_back_with_nothing(
    capsys, monkeypatch
):
    monkeypatch.setattr(
        view,
        "distill",
        lambda capture, bridge=None: View(
            capture.handle, "iki", 1, 9, "a-model", 7, unanswered=6
        ),
    )
    cli.main(_run("print('bir')"))
    handle = capsys.readouterr().err.split()[1]

    saving = store.load_saving(handle)
    assert saving is not None
    assert saving.unanswered == 6


def test_the_footer_carries_the_handle_that_peek_needs(capsys):
    cli.main(_run("print('bir')"))
    handle = capsys.readouterr().err.split()[1]

    assert cli.main(["peek", handle]) == 0
    assert capsys.readouterr().out.strip() == "bir"


# -- peek and list ----------------------------------------------------------


def test_peek_returns_the_capture_byte_for_byte(capsys):
    cli.main(_run("for n in range(1, 6): print(f'satir {n}')"))
    handle = capsys.readouterr().err.split()[1]

    assert cli.main(["peek", handle, "2", "4"]) == 0
    said = capsys.readouterr()
    assert said.out.splitlines() == ["satir 2", "satir 3", "satir 4"]
    assert "lines 2-4 of 5" in said.err


def test_peek_without_a_handle_is_an_error(capsys):
    assert cli.main(["peek"]) == 2
    assert "needs a handle" in capsys.readouterr().err


def test_peek_at_a_handle_that_was_never_captured_fails_without_a_traceback(capsys):
    assert cli.main(["peek", "yoktur"]) == 1
    assert "sift:" in capsys.readouterr().err


def test_list_shows_what_was_run_and_how_it_ended(capsys):
    cli.main(_run(FAILING))
    handle = capsys.readouterr().err.split()[1]

    assert cli.main(["list"]) == 0
    said = capsys.readouterr().out
    assert handle in said
    assert "exit 3" in said


def test_list_of_an_empty_store_says_nothing_rather_than_failing(capsys):
    assert cli.main(["list"]) == 0
    assert capsys.readouterr().out == ""


# -- Faz 8: what the shortening cost, and what it saved ---------------------


def test_stats_of_an_empty_store_says_so_rather_than_failing(capsys):
    assert cli.main(["stats"]) == 0
    assert "nothing to add up" in capsys.readouterr().out


def test_a_bill_that_cannot_be_written_costs_the_report_and_nothing_else(
    monkeypatch, tmp_path
):
    """The one part of this tool that is allowed to fail without saying so.

    A cache swept up between the run and the view is not a reason for the caller
    to lose the view they asked for. Reproduced by pointing the bill at a
    directory that is not there, which is what a sweep leaves behind.

    Asked of `best_view` rather than of `cli.main`, on purpose. The command line
    puts its own net under the whole view (`the view is optional; the output is
    not`), and a rule tested through that net would pass whether store keeps its
    promise or not. This is store's promise, so it is asked of store's caller.
    """
    monkeypatch.setattr(store, "view_path", lambda handle: tmp_path / "gone" / "view.json")
    got = capture.run([sys.executable, "-c", "print('bir')"])

    built, _who = view.best_view(got)

    assert "bir" in built.text
    assert store.savings() == [], "the row is what was lost, and only the row"


def test_a_run_writes_down_what_its_view_cost(capsys):
    assert cli.main(_run("for n in range(60): print(f'satir {n}')")) == 0
    shown = capsys.readouterr().out

    (meta, saving), = store.savings()
    assert saving.handle == meta.handle
    assert saving.total == 60
    assert saving.raw_bytes == meta.byte_count
    # The bill is for the view that was printed, not for one recomputed later.
    assert saving.shown_bytes == len(shown.rstrip("\n").encode("utf-8"))
    assert saving.shown_bytes < saving.raw_bytes


def test_a_view_nobody_chose_is_billed_too(capsys):
    """A report that counted only the good runs would flatter the tool.

    Every test in this file runs with no key, so this view came from the ends of
    the capture. It cost the caller whatever it cost them, and it is counted.
    """
    assert cli.main(_run("for n in range(60): print(n)")) == 0
    capsys.readouterr()

    (_, saving), = store.savings()
    assert saving.model is None
    assert saving.asks == 0
    assert saving.shown_bytes > 0


def test_a_capture_nobody_viewed_is_left_out_rather_than_counted_as_free():
    """Counting it would credit the tool for output it never shortened."""
    capture.run([sys.executable, "-c", "print('bir')"])

    assert len(store.recent()) == 1
    assert store.savings() == []


def test_stats_adds_the_runs_up_and_says_where_the_rest_of_it_is(capsys):
    assert cli.main(_run("for n in range(200): print(f'satir {n}')")) == 0
    assert cli.main(_run("for n in range(300): print(f'baska {n}')")) == 0
    capsys.readouterr()

    assert cli.main(["stats"]) == 0
    said = capsys.readouterr().out
    assert "2 runs ·" in said
    assert "on disk, not gone" in said

    raw = sum(s.raw_bytes for _, s in store.savings())
    shown = sum(s.shown_bytes for _, s in store.savings())
    assert f"{raw:,} B captured" in said
    assert f"{shown:,} B shown" in said


def test_a_report_that_cannot_be_written_costs_nothing(capsys, tmp_path, monkeypatch):
    """The bookkeeping is the only part of this tool nobody asked for.

    A read-only cache or a directory swept up between the run and the view must
    cost the report and stop there -- not the output, and not the exit code.
    """
    monkeypatch.setattr(
        store, "view_path", lambda handle: tmp_path / "yok" / "olmayan" / "view.json"
    )

    assert cli.main(_run("print('bir')")) == 0
    assert "bir" in capsys.readouterr().out
    assert store.savings() == []
