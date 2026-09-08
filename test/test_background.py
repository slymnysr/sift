"""Faz 9 -- a command left running, and the part of it nobody has read yet.

Three things are being defended here, and they fail in different ways.

The **record** has to survive the process that wrote it, because every `sift`
invocation is a new one. The **slice** has to hand a reader each line exactly
once, with the number that line has in the whole run -- a slice that renumbers
from 1 sends `sift peek` to the wrong line, which is the one thing this tool
promises cannot happen. And **stopping** has to end the whole tree, because a
command killed alone leaves children writing to a file nobody is reading.

The last of those is proved against real processes rather than against a fake.
A test that mocks `os.killpg` proves that `os.killpg` was called, which is not
the claim being made.
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from sift import background, store, view, watch
from test_distill import _Judge

SLEEPER = "import time; time.sleep(30)"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """A store of its own, no key anywhere, and nothing left running afterwards.

    The teardown is not tidiness. These tests start real detached processes; one
    that outlived a failing test would go on holding a terminal open long after
    the run that started it had been forgotten.
    """
    monkeypatch.setenv("SIFT_HOME", str(tmp_path / "sift"))
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("SIFT_API_KEY", "NVIDIA_API_KEY", "SIFT_MODELS", "SIFT_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    yield
    for left in store.started():
        background.stop(left.handle)


class _Bridge(_Judge):
    """The fake model, plus the one thing the view layer asks the bridge itself.

    `last_error` is how `best_follow` tells "answered, and named no lines" apart
    from "was never reached at all". A fake without it cannot exercise that
    choice, and the choice is the whole difference between a quiet minute and a
    broken endpoint.
    """

    def __init__(self, *replies, error: str | None = None, **rest) -> None:
        super().__init__(*replies, **rest)
        self.last_error = error


def _until(condition, limit: float = 10.0) -> bool:
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


def _write(handle: str, text: str | bytes) -> None:
    """Add to a capture the way a command does: appended, and never rewritten."""
    store.begin(handle)
    data = text.encode("utf-8") if isinstance(text, str) else text
    with open(store.raw_path(handle), "ab") as sink:
        sink.write(data)


def _running(handle: str = "aaaa1111", pid: int = -1) -> store.Running:
    return store.Running(
        handle=handle,
        command=["make", "-j8"],
        shell=False,
        cwd="/tmp",
        started_at=100.0,
        pid=pid,
    )


# -- the record: what survives the process that wrote it --------------------


def test_a_command_left_going_is_remembered_after_the_process_that_started_it():
    store.begin("aaaa1111")
    store.mark_running(_running())
    assert store.load_running("aaaa1111") == _running()


def test_a_finished_run_is_not_running_however_the_marker_reads():
    """The marker is removed at the end, and a process killed hard never gets to.

    So the two records are not equal witnesses: `meta.json` is written once, by
    something that watched the command end, and it wins. Without this rule a
    supervisor killed with SIGKILL leaves a handle that reads `running` for as
    long as its directory survives.
    """
    store.begin("aaaa1111")
    store.mark_running(_running())
    store.finish(
        store.Meta(
            handle="aaaa1111",
            command=["make", "-j8"],
            shell=False,
            exit_code=0,
            timed_out=False,
            started_at=100.0,
            duration_s=1.0,
            byte_count=0,
            cwd="/tmp",
        )
    )
    assert store.load_running("aaaa1111") is None


def test_a_marker_that_cannot_be_read_is_not_a_command_still_running():
    store.begin("aaaa1111")
    store.running_path("aaaa1111").write_text("{ this is not json", encoding="utf-8")
    assert store.load_running("aaaa1111") is None


def test_a_marker_missing_half_its_fields_is_not_a_command_still_running():
    store.begin("aaaa1111")
    store.running_path("aaaa1111").write_text(json.dumps({"handle": "aaaa1111"}), "utf-8")
    assert store.load_running("aaaa1111") is None


def test_every_command_left_going_is_listed_newest_first():
    for name, when in (("aaaa1111", 100.0), ("bbbb2222", 300.0), ("cccc3333", 200.0)):
        store.begin(name)
        store.mark_running(
            store.Running(
                handle=name, command=["x"], shell=False, cwd="/tmp", started_at=when, pid=-1
            )
        )
    assert [r.handle for r in store.started()] == ["bbbb2222", "cccc3333", "aaaa1111"]


def test_forgetting_a_marker_that_was_never_there_is_not_an_error():
    store.begin("aaaa1111")
    store.clear_running("aaaa1111")
    store.clear_running("aaaa1111")


# -- the cursor: how much of it a reader has been handed --------------------


def test_a_capture_nobody_has_read_starts_at_the_beginning():
    assert store.load_cursor("aaaa1111") == store.Cursor(bytes=0, lines=0)


def test_a_cursor_that_cannot_be_read_starts_over_rather_than_raising():
    """Being shown a line twice costs patience; being shown none costs the output.

    So an unreadable bookmark is the same answer as no bookmark at all. The
    alternative -- refusing to read the capture because the note about it is
    damaged -- fails in the expensive direction.
    """
    store.begin("aaaa1111")
    store.cursor_path("aaaa1111").write_text("not json at all", encoding="utf-8")
    assert store.load_cursor("aaaa1111") == store.Cursor(bytes=0, lines=0)


def test_a_cursor_that_cannot_be_written_costs_the_bookmark_and_nothing_else(monkeypatch):
    """Moving the bookmark must never be what loses the reader their output.

    Asked of `save_cursor` and not through a command, on purpose: every caller
    above this has its own net under the whole look, and a rule tested through
    one of those nets passes whether or not this promise is kept.
    """
    monkeypatch.setattr(store, "cursor_path", lambda handle: store.home() / "gone" / "x.json")
    store.save_cursor("aaaa1111", store.Cursor(bytes=5, lines=1))


# -- the slice: every line once, numbered as part of the whole run ----------


def test_a_look_returns_what_has_arrived_since_the_last_one():
    _write("aaaa1111", "bir\niki\n")
    found, first, moved = background.unread("aaaa1111")
    assert (found, first) == (["bir", "iki"], 1)

    background.seen("aaaa1111", moved)
    _write("aaaa1111", "uc\n")
    assert background.unread("aaaa1111")[0] == ["uc"]


def test_the_numbering_carries_on_from_where_the_reader_stopped():
    """The reason a follow is a slice of one capture and not a capture of its own.

    Line 3 has to still be line 3 when it is reached through `sift peek`, or the
    numbers in a view point at a file that disagrees with them.
    """
    _write("aaaa1111", "bir\niki\n")
    background.seen("aaaa1111", background.unread("aaaa1111")[2])
    _write("aaaa1111", "uc\ndort\n")

    found, first, moved = background.unread("aaaa1111")
    assert (found, first) == (["uc", "dort"], 3)
    assert moved == store.Cursor(bytes=len("bir\niki\nuc\ndort\n"), lines=4)


def test_the_line_being_written_right_now_is_left_for_the_next_look():
    """Half a line shown now would arrive as two lines that never existed.

    The command is mid-write: what follows the last newline is not a line yet.
    Showing it would present a fragment as whole, and its other half would turn
    up in the next look looking like a line of its own.
    """
    _write("aaaa1111", "tam\nyari")
    found, _first, moved = background.unread("aaaa1111")
    assert found == ["tam"]

    background.seen("aaaa1111", moved)
    _write("aaaa1111", "m\n")
    assert background.unread("aaaa1111")[0] == ["yarim"]


def test_a_look_with_nothing_whole_in_it_yet_is_an_empty_look():
    _write("aaaa1111", "hic bitmemis satir")
    assert background.unread("aaaa1111") == ([], 1, store.Cursor(0, 0))


def test_a_character_split_across_two_looks_is_never_shown_broken():
    """Cutting at a newline is also what keeps the decoding whole.

    A newline byte cannot be part of a multi-byte character, so a slice that
    ends at one ends at a character boundary. Without that rule a look taken
    mid-character would show a replacement mark for a letter that arrived
    perfectly well a millisecond later.
    """
    _write("aaaa1111", b"\xc3\xbc\xc3")  # "ü" and the first byte of "ç"
    assert background.unread("aaaa1111")[0] == []

    _write("aaaa1111", b"\xa7\n")
    found, _first, _moved = background.unread("aaaa1111")
    assert found == ["üç"]
    assert "�" not in found[0]


def test_a_capture_with_no_bytes_yet_is_an_empty_look_and_not_an_error():
    assert background.unread("aaaa1111") == ([], 1, store.Cursor(0, 0))


def test_a_look_is_not_a_read_until_the_reader_has_been_handed_it():
    """`unread` returns the new cursor; it does not save it.

    Saving it there would mark lines read before anything had been done with
    them, and a view that then failed to build would take them with it -- output
    nobody saw and nobody can ask for again.
    """
    _write("aaaa1111", "bir\n")
    background.unread("aaaa1111")
    assert background.unread("aaaa1111")[0] == ["bir"]


# -- the supervisor: the ending nobody else was there to see ----------------


def test_the_supervisor_runs_the_command_and_writes_down_how_it_ended():
    code = watch.watch(
        "aaaa1111",
        [
            sys.executable,
            "-c",
            f"import sys; sys.stdout.buffer.write({b'merhaba\n'!r});"
            " raise SystemExit(3)",
        ],
        started_at=store.now(),
    )
    meta = store.load("aaaa1111")
    assert code == 3
    assert meta is not None and meta.exit_code == 3
    assert store.read_raw("aaaa1111") == b"merhaba\n"
    assert meta.byte_count == 8


def test_a_command_that_could_not_start_is_recorded_rather_than_left_running():
    """There is nobody to raise at out here.

    `sift run` hands an OSError back to the caller, who is standing right there.
    A background launch has already returned; the only process that knows the
    command never started is this one, and a handle left marked running is worse
    than a handle marked failed.
    """
    code = watch.watch("aaaa1111", ["boyle-bir-komut-yok-ndrs"], started_at=store.now())
    meta = store.load("aaaa1111")
    assert code == 127
    assert meta is not None and meta.exit_code == 127


def test_the_marker_comes_down_once_the_ending_has_been_written():
    store.begin("aaaa1111")
    store.mark_running(_running())
    watch.watch("aaaa1111", [sys.executable, "-c", "pass"], started_at=store.now())
    assert not store.running_path("aaaa1111").is_file()


def test_the_ending_is_written_before_the_marker_comes_down(monkeypatch):
    """The order is the whole point, and only one of the two orders has an answer.

    A reader arriving between the two writes sees, in this order, a capture that
    is finished and still marked running -- which `load_running` answers
    correctly. The other order leaves a moment where the run is neither running
    nor finished, and a caller waiting on it is told there is nothing to wait for.
    """
    store.begin("aaaa1111")
    store.mark_running(_running())
    order: list[bool] = []
    real = store.finish
    monkeypatch.setattr(
        store,
        "finish",
        lambda meta: (order.append(store.running_path(meta.handle).is_file()), real(meta))[1],
    )
    watch.watch("aaaa1111", [sys.executable, "-c", "pass"], started_at=store.now())
    assert order == [True], "the marker was taken down before the ending was written"


def test_the_supervisor_adds_to_a_capture_rather_than_starting_it_over():
    _write("aaaa1111", "onceki\n")
    yazar = f"import sys; sys.stdout.buffer.write({b'sonraki\n'!r})"
    watch.watch("aaaa1111", [sys.executable, "-c", yazar], started_at=store.now())
    assert store.read_raw("aaaa1111") == b"onceki\nsonraki\n"


# -- launching, and ending what was launched --------------------------------


def test_a_launched_command_goes_on_running_after_the_launcher_returns():
    started = background.launch([sys.executable, "-c", SLEEPER])
    assert background.alive(started)
    assert store.load_running(started.handle) == started
    assert [r.handle for r in store.started()] == [started.handle]


def test_a_launched_command_is_read_while_it_runs():
    code = "print('ilk', flush=True); import time; time.sleep(30)"
    started = background.launch([sys.executable, "-c", code])
    assert _until(lambda: background.unread(started.handle)[0] == ["ilk"])


def test_stopping_a_run_ends_it_and_writes_down_that_it_was_ended():
    """A signal is not an ending until somebody writes it down.

    The exit code is the one the operating system reports for a process killed
    by a signal, because that is what happened -- and because `Meta.failed`
    already reads it correctly, where a cleared exit code would say the command
    succeeded.
    """
    started = background.launch([sys.executable, "-c", SLEEPER])
    meta = background.stop(started.handle)

    assert meta is not None and meta.exit_code is not None and meta.exit_code < 0
    assert meta.failed
    assert store.load_running(started.handle) is None
    assert not background.alive(started)


@pytest.mark.skipif(sys.platform == "win32", reason="no process groups to end there")
def test_stopping_a_run_ends_what_the_command_itself_started(tmp_path):
    """The reason the supervisor and the command share one process group.

    A build leaves compilers behind and a test runner leaves workers. Killing
    only the process named on the command line leaves those running, writing to
    a file nobody is reading -- so the proof is a grandchild that goes on
    writing until something stops it, and the check is that it stopped.
    """
    ticking = tmp_path / "ticking"
    child = tmp_path / "child.py"
    child.write_text(
        "import time\n"
        f"path = {str(ticking)!r}\n"
        "while True:\n"
        "    open(path, 'a').write('tick\\n')\n"
        "    time.sleep(0.05)\n",
        encoding="utf-8",
    )
    parent = tmp_path / "parent.py"
    parent.write_text(
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, {str(child)!r}])\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )

    started = background.launch([sys.executable, str(parent)])
    assert _until(lambda: ticking.is_file() and ticking.stat().st_size > 0), "no grandchild"

    background.stop(started.handle)
    settled = ticking.stat().st_size
    time.sleep(0.5)
    assert ticking.stat().st_size == settled, "the grandchild outlived the run it belonged to"


def test_stopping_a_run_that_has_already_finished_changes_nothing():
    """Stopping something that has stopped is not an error, and not a rewrite.

    Replacing the ending here would swap a real exit code for a guess about a
    signal nobody sent.
    """
    started = background.launch([sys.executable, "-c", "print('bitti')"])
    assert _until(lambda: store.load(started.handle) is not None)

    before = store.load(started.handle)
    assert background.stop(started.handle) == before


def test_a_handle_nobody_ever_started_has_nothing_to_stop():
    assert background.stop("yokboyle") is None


def test_a_run_whose_supervisor_is_gone_is_closed_rather_than_left_open():
    """A lost run is not a running one, and it is not a finished one either.

    Nobody knows how it came out, so nothing is claimed about how it came out --
    the exit code stays empty. What matters is that the handle stops reading
    `running` forever, because a reader waiting on that is waiting for an ending
    no process is left to write.
    """
    store.begin("aaaa1111")
    store.mark_running(_running(pid=-1))
    meta = background.stop("aaaa1111")

    assert meta is not None and meta.exit_code is None
    assert store.load_running("aaaa1111") is None


def test_a_run_whose_supervisor_is_gone_is_called_lost_and_not_running():
    """Three states, and the middle one is the whole reason this word exists.

    A run that finished has an ending to report. A run still going says so. A
    run whose supervisor is gone without having written an ending is neither,
    and calling it `running` would leave a reader waiting for something nobody
    is left to write.
    """
    assert view.state(_running(pid=-1), None) == "lost"
    assert view.state(None, None) == "unknown"
    assert view.state(None, _meta(exit_code=0)) == "exit 0"
    assert view.state(None, _meta(exit_code=None, timed_out=True)) == "timed out"


def _meta(*, exit_code: int | None, timed_out: bool = False) -> store.Meta:
    return store.Meta(
        handle="aaaa1111",
        command=["make"],
        shell=False,
        exit_code=exit_code,
        timed_out=timed_out,
        started_at=100.0,
        duration_s=1.0,
        byte_count=0,
        cwd="/tmp",
    )


def test_a_pid_that_is_not_there_is_not_a_run_still_going():
    assert not background.alive(_running(pid=-1))


@pytest.mark.skipif(not Path("/proc").is_dir(), reason="no /proc to read a state from")
def test_a_supervisor_that_has_exited_is_not_still_watching():
    """A zombie answers every other check exactly as a healthy process does.

    It keeps its pid, its group, and its reply to signal 0. It is watching
    nothing. The case is real rather than academic: a caller that launches a
    command and stays alive -- the MCP server does -- would otherwise be told
    that a supervisor killed hard is still running, for as long as it lives.
    """
    child = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    assert _until(lambda: child.poll() is None or _dead_but_listed(child.pid))
    child.wait(timeout=10)  # only now is it collected

    assert not background.alive(_running(pid=child.pid))


def _dead_but_listed(pid: int) -> bool:
    """True once the process has exited but its entry is still there."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            stat = f.read()
    except OSError:
        return False
    cut = stat.rfind(b")")
    return cut > 0 and stat[cut + 1 :].strip()[:1] == b"Z"


def test_a_marker_naming_pid_one_is_closed_and_never_signalled():
    """The rule this test file learned the expensive way.

    An earlier version wrote its fake markers with pid 1. `alive` asked the
    kernel whether pid 1 was there, was told "yes, but not yours", counted that
    as running, and the teardown called `stop` -- which signals a process
    *group*. `os.killpg(os.getpgid(1))` is process group 1, and on the machine
    this was written on it took down the terminal multiplexer, a detached
    watchdog, and the session running the tests.

    So the promise is not "stop the right process". It is: a pid this tool did
    not start is never signalled at all, and the run is closed as lost instead.
    """
    store.begin("aaaa1111")
    store.mark_running(_running(pid=1))

    assert not background.ours(_running(pid=1))
    assert not background.alive(_running(pid=1))

    meta = background.stop("aaaa1111")
    assert meta is not None
    assert meta.exit_code is None, "a run nobody could signal has no ending to claim"
    assert store.load_running("aaaa1111") is None


@pytest.mark.skipif(sys.platform == "win32", reason="killpg yok, yayin da yok")
def test_signalling_refuses_a_broadcast_whatever_asked_for_it(monkeypatch):
    """The second guard, tested apart from the first, because that is its job.

    `ours` refuses these pids and `_signal` refuses them again. Testing only the
    pair together would pass with either one of them gone, which is the state
    this exists to make impossible: one guard is one edit away from `kill(-1)`.

    And `kill(-1)` is what these are. `os.killpg(g, s)` is `kill(-g, s)`, so a
    pid of 1 is not process group 1 -- POSIX hands it to every process the
    caller may signal, init excepted. A pid of 0 is quieter and no better:
    `getpgid(0)` answers with the caller's own group.

    So nothing may leave here for a pid below 2. Not a narrower signal, not a
    fallback: nothing.
    """
    sent: list[tuple[str, int, int]] = []
    monkeypatch.setattr("os.killpg", lambda g, n: sent.append(("killpg", g, n)))
    monkeypatch.setattr("os.kill", lambda p, n: sent.append(("kill", p, n)))

    for pid in (1, 0, -1, -1000):
        background._signal(pid, signal.SIGTERM)

    assert sent == [], f"a broadcast left the building: {sent}"


@pytest.mark.skipif(sys.platform == "win32", reason="no process groups there")
def test_a_group_that_is_a_broadcast_is_narrowed_to_the_process_itself(monkeypatch):
    """The other half of the floor, and it escaped the battery until it was written.

    Refusing `pid <= 1` is not enough on its own. The pid that arrives here can
    be an ordinary one whose *group* answers 1, and `killpg(1, ...)` is the same
    broadcast whichever number led to it. So the group is checked on its own
    terms, and when it is one the signal is narrowed to the pid rather than
    dropped -- there is a real process there and ending it is still the job.

    Written because the mutation battery caught the guard being unguarded: with
    `if group > 1` replaced by `if True`, all 534 tests still passed. A rule
    nothing objects to is not a rule.
    """
    sent: list[tuple[str, int, int]] = []
    monkeypatch.setattr("os.getpgid", lambda pid: 1)
    monkeypatch.setattr("os.killpg", lambda g, n: sent.append(("killpg", g, n)))
    monkeypatch.setattr("os.kill", lambda p, n: sent.append(("kill", p, n)))

    background._signal(4242, signal.SIGTERM)

    assert sent == [("kill", 4242, signal.SIGTERM)], (
        f"a group of 1 must never be signalled as a group: {sent}"
    )


@pytest.mark.skipif(sys.platform == "win32", reason="no process groups to lead there")
def test_a_process_that_did_not_lead_its_own_session_is_not_our_supervisor():
    """`launch` always starts a session leader, so anything else is a stranger.

    A plain child inherits the group of whoever started it, which is exactly the
    shape a reused pid has -- alive, signallable, and nothing to do with this
    run. Signalling its group would hit the process that started the test.
    """
    stranger = subprocess.Popen([sys.executable, "-c", SLEEPER])
    try:
        assert not background.ours(_running(pid=stranger.pid))
        assert not background.alive(_running(pid=stranger.pid))
    finally:
        stranger.kill()
        stranger.wait(timeout=10)


# -- what a look is allowed to say about itself -----------------------------


def test_a_look_with_no_new_lines_asks_nobody_anything(monkeypatch):
    """Nothing new is an answer, and it costs nothing to give.

    A look that reached for a model to be told about zero lines would spend an
    ask, and a second of the caller's time, to say what was already known before
    the request was built.
    """
    monkeypatch.setattr(view, "Bridge", lambda: pytest.fail("asked about nothing"))
    built, who = view.best_follow("aaaa1111", [], 5)
    assert (built.total, built.text, who) == (0, "", "nothing new")


def test_lines_a_model_read_and_chose_none_of_are_folded_and_not_dropped(monkeypatch):
    """A quiet minute of a build comes back as nothing, and says how much nothing.

    This is the one place a follow parts company with a finished capture. There,
    an answer naming no lines means something went wrong and the ends are shown
    instead; here it is the honest report of a stretch that was only progress.
    """
    monkeypatch.setattr(view, "Bridge", lambda: _Bridge(""))
    built, who = view.best_follow("aaaa1111", ["yuzde 1", "yuzde 2"], 40)

    assert built.kept == 0
    assert built.total == 2
    assert "2 lines not shown" in built.text
    assert "nothing new worth showing" in who


def test_a_look_that_could_not_reach_a_model_still_shows_the_lines(monkeypatch):
    monkeypatch.setattr(view, "Bridge", lambda: _Bridge(None, error="busy"))
    built, who = view.best_follow("aaaa1111", ["bir", "iki"], 40)

    assert "bir" in built.text and "iki" in built.text
    assert "busy" in who


def test_the_numbers_in_a_look_are_the_numbers_of_the_whole_run(monkeypatch):
    """The claim the whole design of this phase rests on.

    The model is shown lines 810 onwards and answers `812`. The line that comes
    back has to be the third of the slice -- the one that is line 812 of the
    capture -- because that number is what a reader will type into `sift peek`.
    """
    judge = _Bridge("812")
    monkeypatch.setattr(view, "Bridge", lambda: judge)
    built, _who = view.best_follow("aaaa1111", ["ilk", "orta", "aranan", "son"], 810)

    assert "aranan" in built.text
    assert "ilk" not in built.text and "son" not in built.text
    assert "810| ilk" in judge.prompt, "the model was not shown the run's own numbers"
    assert "1| ilk" not in judge.prompt, "the slice was numbered from its own start"


def test_nothing_before_the_first_new_line_is_marked_as_missing(monkeypatch):
    """What came before was already handed over, and is not a gap in this look.

    Marking it would tell the reader they had missed nine hundred lines that
    they were shown, one look ago, on purpose.
    """
    monkeypatch.setattr(view, "Bridge", lambda: _Bridge("901"))
    built, _who = view.best_follow("aaaa1111", ["bir", "iki"], 900)

    assert "900 lines not shown" not in built.text
    assert "899 lines not shown" not in built.text
