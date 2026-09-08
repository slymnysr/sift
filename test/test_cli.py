"""Faz 4 -- the command line, and the promise that it cannot break your command.

Every test here runs with no API key and no network, which is the state the
third rule in the README is about. What the model would add is tested elsewhere;
what has to work without it is tested here.
"""

from __future__ import annotations

import sys
import time

import pytest

from sift import background, capture, cli, store, view
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


@pytest.fixture(autouse=True)
def _nothing_outlives_a_test():
    """Whatever a test leaves running, it leaves running for the length of a test.

    These are real detached processes. One that survived a failing assertion
    would keep writing to a capture nobody reads, on a machine nobody is
    watching, for as long as the machine is up.
    """
    yield
    for left in store.started():
        background.stop(left.handle)


def _until(condition, limit: float = 15.0) -> bool:
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


def _talks_then_waits(count: int = 3) -> str:
    """A command that says its piece and then does not end, like a dev server."""
    return (
        f"for n in range({count}): print(f'satir {{n}}', flush=True)\n"
        "import time; time.sleep(60)"
    )


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

    def explode(capture, bridge=None, budget=None, keep=None):
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

    def explode(capture, bridge=None, budget=None, keep=None):
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
        lambda capture, bridge=None, budget=None, keep=None: View(
            capture.handle, "iki", 1, 9, "a-model", 1
        ),
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
        lambda capture, bridge=None, budget=None, keep=None: View(
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
        lambda capture, bridge=None, budget=None, keep=None: View(
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


# -- Faz 9: a command left running -------------------------------------------


def test_the_usage_names_the_commands_for_a_run_left_going(capsys):
    assert cli.main([]) == 0
    said = capsys.readouterr().out
    assert "--background" in said
    assert "sift follow" in said
    assert "sift stop" in said


def test_a_background_run_hands_back_a_handle_and_the_prompt(capsys):
    """The whole point of the flag: the caller gets their shell back.

    The handle goes to stdout on its own, so a script can catch it in a
    variable; everything this tool says about itself goes to stderr, as it does
    everywhere else.
    """
    assert cli.main(_run(_talks_then_waits(), "--background")) == 0

    said = capsys.readouterr()
    handle = said.out.strip()
    assert handle and " " not in handle
    assert store.load_running(handle) is not None
    assert f"sift follow {handle}" in said.err


def test_a_background_run_refuses_a_timeout_rather_than_dropping_it(capsys):
    """Nothing is left waiting to enforce one, and saying nothing would be a lie.

    A caller who believes a limit is in place when none is has been told
    something untrue about their own command, which is how a build runs all
    night.
    """
    assert cli.main(_run("pass", "--background", "--timeout", "5")) == 2
    assert "do not go together" in capsys.readouterr().err
    assert store.started() == []


def test_following_shows_what_arrived_and_does_not_show_it_twice(capsys):
    """The rule the cursor exists for: each line is handed over exactly once."""
    assert cli.main(_run(_talks_then_waits(), "--background")) == 0
    handle = capsys.readouterr().out.strip()
    assert _until(lambda: b"satir 2" in store.read_raw(handle))

    assert cli.main(["follow", handle]) == 0
    first = capsys.readouterr()
    assert "satir 0" in first.out
    assert "satir 2" in first.out
    # The numbers a reader would type into `sift peek`, not a count of the slice.
    assert "new lines 1-" in first.err

    assert cli.main(["follow", handle]) == 0
    again = capsys.readouterr()
    assert "satir 0" not in again.out
    assert "nothing new since the last look" in again.err


def test_following_with_no_handle_follows_the_newest_run(capsys):
    """What somebody who started one thing and walked away actually types."""
    assert cli.main(_run(_talks_then_waits(), "--background")) == 0
    handle = capsys.readouterr().out.strip()
    assert _until(lambda: b"satir 2" in store.read_raw(handle))

    assert cli.main(["follow"]) == 0
    assert "satir 1" in capsys.readouterr().out


def test_following_when_nothing_is_running_says_so(capsys):
    assert cli.main(["follow"]) == 1
    assert "nothing is running" in capsys.readouterr().err


def test_following_a_handle_that_was_never_started_is_an_error(capsys):
    assert cli.main(["follow", "yokboyle"]) == 1
    assert "no such run" in capsys.readouterr().err


def test_a_finished_background_run_gives_back_the_commands_own_exit_code(capsys):
    """Wrapping a command in `sift` changes what you read, never what it returned.

    The promise `sift run` makes has to survive the command being started one
    day and read the next, or a script that waits on a background build cannot
    tell whether it passed.
    """
    assert cli.main(_run("raise SystemExit(3)", "--background")) == 0
    handle = capsys.readouterr().out.strip()
    assert _until(lambda: store.load(handle) is not None)

    assert cli.main(["follow", handle]) == 3
    assert "exit 3" in capsys.readouterr().err


def test_stopping_a_run_ends_it_and_says_how_it_ended(capsys):
    assert cli.main(_run(_talks_then_waits(), "--background")) == 0
    handle = capsys.readouterr().out.strip()

    assert cli.main(["stop", handle]) == 0
    said = capsys.readouterr().err
    assert handle in said
    assert "B captured" in said
    assert store.load_running(handle) is None
    assert store.load(handle) is not None


def test_stopping_when_nothing_is_running_says_so(capsys):
    assert cli.main(["stop"]) == 1
    assert "nothing is running" in capsys.readouterr().err


def test_the_listing_puts_what_is_still_running_first(capsys):
    """Running first because it is the part that can still be acted on."""
    assert cli.main(_run("print('bitti')")) == 0  # a finished capture
    capsys.readouterr()
    assert cli.main(_run(_talks_then_waits(), "--background")) == 0
    handle = capsys.readouterr().out.strip()

    assert cli.main(["list"]) == 0
    rows = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert rows[0].startswith(handle)
    assert "running" in rows[0]

# -- Faz 12: the caller's own say, at the terminal ----------------------------


def test_keep_shows_a_line_whatever_else_was_chosen(capsys):
    assert cli.main(_run("print('bir'); print('ARANAN'); print('uc')", "--keep", "ARANAN")) == 0
    assert "ARANAN" in capsys.readouterr().out


def test_a_budget_the_caller_gave_is_the_budget_that_is_spent(capsys):
    """Not a suggestion. The number the caller typed is the number in the footer."""
    code = "for n in range(40): print(f'satir {n}')"
    assert cli.main(_run(code, "--budget", "5")) == 0
    assert "/40 lines" in capsys.readouterr().err


def test_a_command_runs_where_the_caller_said(capsys, tmp_path):
    (tmp_path / "isaret.txt").write_text("burada", encoding="utf-8")
    code = "import os; print(sorted(os.listdir('.')))"

    assert cli.main(_run(code, "--cwd", str(tmp_path))) == 0
    assert "isaret.txt" in capsys.readouterr().out


def test_an_outline_takes_the_same_two_words(capsys, tmp_path):
    source = tmp_path / "ornek.py"
    source.write_text("def bir():\n    pass\n\n\ndef ARANAN():\n    pass\n", encoding="utf-8")

    assert cli.main(["outline", "--keep", "ARANAN", str(source)]) == 0
    assert "ARANAN" in capsys.readouterr().out

# -- Faz 14: the way into a gap when you know the word ------------------------


def test_a_search_returns_the_matching_lines_and_their_neighbours(capsys):
    code = "\n".join(f"print('satir {n}')" for n in range(1, 41)) + "\nprint('ARANAN')"
    assert cli.main(_run(code)) == 0
    handle = _handle_of(capsys.readouterr().err)

    assert cli.main(["peek", handle, "--grep", "ARANAN", "--around", "2"]) == 0
    said = capsys.readouterr()
    assert "ARANAN" in said.out
    assert "satir 39" in said.out, "the lines around the match are the point"
    assert "satir 1" not in said.out
    assert "1 line matched" in said.err


def test_a_search_that_finds_nothing_says_nothing_rather_than_everything(capsys):
    assert cli.main(_run("print('bir')")) == 0
    handle = _handle_of(capsys.readouterr().err)

    assert cli.main(["peek", handle, "--grep", "YOKBOYLE"]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_a_pattern_that_will_not_compile_is_searched_for_as_text(capsys):
    assert cli.main(_run("print('void main() {')")) == 0
    handle = _handle_of(capsys.readouterr().err)

    assert cli.main(["peek", handle, "--grep", "main("]) == 0
    assert "main()" in capsys.readouterr().out


def test_a_search_says_how_many_matched_and_not_only_how_many_it_shows(capsys):
    """Two different numbers, and a reader needs both.

    Context is added around every match and the answer is capped, so "40 lines"
    could be four matches or forty. Only the count of matches says whether what
    came back is all of it.
    """
    code = "\n".join(f"print('TUT {n}')" for n in range(30))
    assert cli.main(_run(code)) == 0
    handle = _handle_of(capsys.readouterr().err)

    assert cli.main(["peek", handle, "--grep", "TUT", "--around", "0", "--max", "5"]) == 0
    said = capsys.readouterr()
    assert "30 lines matched" in said.err
    assert said.out.count("TUT") <= 6, "the cap was not applied"


def _handle_of(footer: str) -> str:
    return footer.split()[1]

# -- Faz 15: several at once --------------------------------------------------


def test_several_files_are_digested_in_one_go(capsys, tmp_path):
    for n in range(3):
        (tmp_path / f"kayit{n}.log").write_text(f"satir {n}\nbaska {n}\n", encoding="utf-8")
    paths = [str(tmp_path / f"kayit{n}.log") for n in range(3)]

    assert cli.main(["digest", *paths]) == 0

    said = capsys.readouterr()
    for n in range(3):
        assert f"satir {n}" in said.out
        assert f"kayit{n}.log" in said.err, "each file must say which one it is"


def test_one_unreadable_file_does_not_take_the_others_with_it(capsys, tmp_path):
    good = tmp_path / "var.log"
    good.write_text("burada\n", encoding="utf-8")

    assert cli.main(["digest", str(good), str(tmp_path / "yok.log")]) == 1

    said = capsys.readouterr()
    assert "burada" in said.out, "the readable file was answered anyway"
    assert "unreadable" in said.err


def test_following_everything_answers_about_every_run(capsys):
    handles = []
    for _ in range(2):
        assert cli.main(_run(_talks_then_waits(), "--background")) == 0
        handles.append(capsys.readouterr().out.strip())
    for handle in handles:
        assert _until(lambda h=handle: b"satir 2" in store.read_raw(h))

    assert cli.main(["follow", "--all"]) == 0

    said = capsys.readouterr()
    for handle in handles:
        assert handle in said.err
    assert said.out.count("satir 0") == 2


def test_waiting_holds_until_a_run_speaks(capsys):
    code = "import time; time.sleep(0.4); print('geldi', flush=True); time.sleep(60)"
    assert cli.main(["run", "--background", "--", sys.executable, "-c", code]) == 0
    handle = capsys.readouterr().out.strip()

    assert cli.main(["follow", handle, "--wait", "15"]) == 0
    assert "geldi" in capsys.readouterr().out

# -- Faz 16: what this machine already knows ----------------------------------


def test_memory_counts_the_runs_and_says_how_they_went(capsys):
    for _ in range(2):
        assert cli.main(_run("print('bir')")) == 0
    assert cli.main(_run("import sys; sys.exit(3)")) == 3
    capsys.readouterr()

    assert cli.main(["memory"]) == 0
    said = capsys.readouterr().out
    assert "exit 0" in said
    assert "exit 3" in said
    assert "runs still on disk" in said


def test_memory_names_a_command_that_has_never_once_worked(capsys):
    """The question somebody actually asks: is this broken, or is it me?"""
    for _ in range(3):
        assert cli.main(_run("import sys; sys.exit(1)")) == 1
    capsys.readouterr()

    assert cli.main(["memory"]) == 0
    assert "never worked here" in capsys.readouterr().out


def test_memory_narrows_to_what_was_asked_about(capsys):
    assert cli.main(_run("print('ARANAN')")) == 0
    assert cli.main(_run("print('baska')")) == 0
    capsys.readouterr()

    assert cli.main(["memory", "ARANAN"]) == 0
    said = capsys.readouterr().out
    assert "ARANAN" in said
    assert "baska" not in said


def test_memory_with_nothing_to_remember_says_so_rather_than_nothing(capsys):
    assert cli.main(["memory"]) == 0
    assert "nothing" in capsys.readouterr().out


def test_memory_asks_no_model_at_all(capsys, monkeypatch):
    """Counting is not judgement, and a request spent on it is a request wasted."""
    assert cli.main(_run("print('bir')")) == 0
    capsys.readouterr()

    # Patched only now: the run above is allowed to ask, the memory below is not.
    monkeypatch.setattr(view, "Bridge", lambda: pytest.fail("memory reached for a model"))
    assert cli.main(["memory"]) == 0

# -- Faz 17: tools that answer without opening the file -----------------------


def test_the_tools_are_listed_with_what_each_replaces(capsys):
    assert cli.main(["tools"]) == 0
    said = capsys.readouterr().out
    for name in ("sg", "diff", "loc"):
        assert name in said
    assert "replaces" in said


def test_a_tool_this_machine_does_not_have_says_what_it_is_called(capsys, monkeypatch):
    """Nothing is installed for anybody. The decision stays with whoever owns the machine."""
    monkeypatch.setattr("shutil.which", lambda name: None)

    assert cli.main(["tool", "sg", "pattern"]) == 127
    said = capsys.readouterr().err
    assert "ast-grep" in said
    assert "not on this machine" in said


def test_a_name_that_is_not_one_of_them_says_which_are(capsys):
    assert cli.main(["tool", "yokboyle"]) == 2
    said = capsys.readouterr().err
    assert "no such tool" in said
    assert "sg" in said and "diff" in said and "loc" in said


def test_a_tool_that_is_here_is_run_and_distilled_like_anything_else(capsys, monkeypatch):
    """The whole point: their output is large by nature, so it goes through the engine."""
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(
        "sift.tools.command_for",
        lambda name, args: [sys.executable, "-c", "print('bulundu')"],
    )
    monkeypatch.setattr("sift.cli.command_for", lambda name, args: [
        sys.executable, "-c", "print('bulundu')"
    ])

    assert cli.main(["tool", "sg", "x"]) == 0
    assert "bulundu" in capsys.readouterr().out
