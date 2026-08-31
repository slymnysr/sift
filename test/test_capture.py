"""Faz 1 -- the command is run here, and nothing it said is lost."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
import uuid

import pytest

from sift import store
from sift.capture import run
from sift.peek import peek


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    """Every test gets its own store, so none of them can see another's captures."""
    monkeypatch.setenv("SIFT_HOME", str(tmp_path / "sift"))
    return tmp_path


def _python(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def test_what_the_command_wrote_comes_back_byte_for_byte():
    cap = run(_python("print('merhaba dunya')"))
    assert cap.text() == "merhaba dunya\n"
    assert cap.meta.exit_code == 0
    assert not cap.meta.failed


def test_the_exit_code_is_reported_rather_than_raised():
    """A failing command is the interesting case, not an error condition.

    Raising here would mean the caller has to catch an exception to see the
    output of the run that actually needed reading.
    """
    cap = run(_python("import sys; sys.exit(3)"))
    assert cap.meta.exit_code == 3
    assert cap.meta.failed


def test_stderr_and_stdout_arrive_in_the_order_a_terminal_would_show_them():
    cap = run(
        _python(
            "import sys\n"
            "print('bir'); sys.stdout.flush()\n"
            "print('iki', file=sys.stderr); sys.stderr.flush()\n"
            "print('uc'); sys.stdout.flush()\n"
        )
    )
    assert cap.text().splitlines() == ["bir", "iki", "uc"]


def test_a_byte_that_is_not_utf8_does_not_stop_the_capture():
    """Build logs contain stray bytes. Refusing to decode one would fail the tool
    exactly where it is most needed."""
    cap = run(_python("import sys; sys.stdout.buffer.write(b'iyi \\xff kotu\\n')"))
    assert "iyi" in cap.text()
    assert "kotu" in cap.text()


def test_output_larger_than_memory_would_like_still_lands_on_disk():
    cap = run(_python("for i in range(20000): print('satir', i)"))
    assert cap.meta.byte_count > 200_000
    assert peek(cap.handle).total_lines == 20000


def test_a_command_that_never_ends_is_stopped_and_says_so():
    started = time.monotonic()
    cap = run(_python("import time\nwhile True: time.sleep(0.05)"), timeout=1.0)
    assert cap.meta.timed_out
    assert cap.meta.failed
    assert time.monotonic() - started < 20


def test_what_a_stopped_command_managed_to_print_is_kept():
    """A timeout is not a reason to lose the output that led up to it."""
    cap = run(
        _python(
            "import sys, time\n"
            "print('basladi'); sys.stdout.flush()\n"
            "while True: time.sleep(0.05)\n"
        ),
        timeout=1.5,
    )
    assert cap.meta.timed_out
    assert "basladi" in cap.text()


def test_peek_returns_the_range_that_was_asked_for():
    cap = run(_python("for i in range(1, 101): print(i)"))
    p = peek(cap.handle, 10, 12)
    assert p.text == "10\n11\n12"
    assert (p.first_line, p.last_line, p.total_lines) == (10, 12, 100)
    assert not p.is_whole


def test_peek_clamps_a_range_instead_of_refusing_it():
    """Someone reading 'lines not shown' guesses at a number. The nearest real
    lines are more use than an error about the guess."""
    cap = run(_python("for i in range(1, 11): print(i)"))
    p = peek(cap.handle, 8, 9999)
    assert p.text.splitlines() == ["8", "9", "10"]
    assert p.last_line == 10


def test_a_capture_can_be_found_again_after_the_process_that_made_it_is_gone():
    cap = run(_python("print('kalici')"))
    again = store.load(cap.handle)
    assert again is not None
    assert again.command == cap.meta.command
    assert store.read_raw(cap.handle) == b"kalici\n"


def test_captures_do_not_collide_when_the_same_command_runs_twice():
    a = run(_python("print('ayni')"))
    b = run(_python("print('ayni')"))
    assert a.handle != b.handle


def test_the_shell_is_available_but_never_the_default():
    cap = run(["echo bir && echo iki"], shell=True)
    assert cap.text().split() == ["bir", "iki"]


def test_a_handle_that_was_never_captured_is_not_an_empty_capture():
    """Two things that look identical on screen and mean opposite things.

    An empty capture is a command that said nothing. A missing handle is a
    question about something that is not here -- usually a typo, or a capture
    made under a different SIFT_HOME. Answering the second with the first sends
    someone looking for a bug in their command.

    An interrupted run is a third case and is not this one: its bytes exist, so
    they are still handed back. Only the claims about them are missing.
    """
    assert store.load("yokboyle") is None
    with pytest.raises(FileNotFoundError):
        store.read_raw("yokboyle")
    with pytest.raises(FileNotFoundError):
        peek("yokboyle")


def test_the_raw_file_holds_the_bytes_and_nothing_added_to_them():
    cap = run(_python("import sys; sys.stdout.buffer.write(b'tam olarak bu')"))
    assert store.raw_path(cap.handle).read_bytes() == b"tam olarak bu"


def test_a_run_is_marked_complete_only_once_it_has_finished():
    """`meta.json` is the marker. Bytes without it are an interrupted run, and
    the bytes are still handed back -- it is the claims about them that are not
    invented."""
    cap = run(_python("print('bitti')"))
    assert store.meta_path(cap.handle).is_file()
    store.meta_path(cap.handle).unlink()
    assert store.load(cap.handle) is None
    assert store.read_raw(cap.handle) == b"bitti\n"


# Two processes: the one `sift` starts, and the one it starts in turn. Both
# carry the token on their command line, which is how the test finds whatever
# outlived the timeout.
_TREE = """\
import subprocess, sys, time
role, token, marker = sys.argv[1], sys.argv[2], sys.argv[3]
if role == "parent":
    subprocess.Popen([sys.executable, __file__, "child", token, marker])
else:
    open(marker, "w").write(token)
time.sleep(60)
"""


def _alive(token: str) -> list[str]:
    """PIDs whose command line carries this token.

    The token is random hex on purpose. An earlier version of this test searched
    for `time.sleep(60)`, and `pgrep -f` reads an extended regular expression:
    the parentheses were a group, so the pattern actually looked for
    `time?sleep60`, which no command line contains. It found nothing whether or
    not the children were killed, and passed either way. Hex has no regex
    meaning, and being unique to one run it also cannot match a process some
    other test -- or some other person on this machine -- happens to be running.
    """
    found = subprocess.run(
        ["pgrep", "-f", token], capture_output=True, text=True, check=False
    )
    return [pid for pid in found.stdout.split() if pid.strip()]


def test_a_timeout_kills_the_children_the_command_started(tmp_path):
    """Killing only the parent leaves orphans writing into a pipe nobody reads."""
    if sys.platform == "win32":
        pytest.skip("Windows'ta surec grubu bu anlamda yok")
    token = uuid.uuid4().hex
    script = tmp_path / "agac.py"
    script.write_text(_TREE, encoding="utf-8")
    marker = tmp_path / "torun.txt"

    cap = run([sys.executable, str(script), "parent", token, str(marker)], timeout=2.0)
    assert cap.meta.timed_out

    try:
        # The grandchild has to have existed for its absence to mean anything. It
        # writes this file before sleeping, so a missing marker would mean the
        # test never set up the situation it claims to check.
        assert marker.read_text(encoding="utf-8") == token, "torun surec hic baslamadi"
        assert not _alive(token), "cocuk surecler timeout'tan sagi cikti"
    finally:
        for pid in _alive(token):  # bu testin artigi baska kosumu bogmasin
            with contextlib.suppress(OSError, ValueError):
                os.kill(int(pid), signal.SIGKILL)


# The same shape, except the grandchild steps into a session of its own. Nothing
# a timeout does to a process group can reach it, so it is the case that decides
# whether `run` is bounded by its deadline or by a stranger's patience.
_ESCAPEE = """\
import subprocess, sys, time
token, marker = sys.argv[1], sys.argv[2]
print("basladi"); sys.stdout.flush()
kacak = (
    "import os, sys, time\\n"
    "os.setsid()\\n"
    "open(sys.argv[2], 'w').write(sys.argv[1])\\n"
    "time.sleep(60)\\n"
)
subprocess.Popen([sys.executable, "-c", kacak, token, marker])
time.sleep(60)
"""


def test_a_process_that_escapes_the_group_cannot_hold_the_run_open(tmp_path):
    """The deadline has to be the tool's, not a stranger's.

    Output is a shared pipe, and it stays open while anyone at all holds the
    writing end. A process that has left the group cannot be killed with it, so
    if reading waited for the pipe to close, `run` would return when that process
    felt like exiting -- an hour later, or never. The bytes it may still write
    are worth less than the promise that a timeout means something.

    Letting go of the pipe is not the same as letting go of what came through
    it. Whatever the command printed before the deadline has to be on disk and
    readable by the time this returns -- otherwise the timeout has cost the
    user the very output they were waiting to read.
    """
    if sys.platform == "win32":
        pytest.skip("Windows'ta oturum kacisi bu bicimde yok")
    token = uuid.uuid4().hex
    script = tmp_path / "kacak.py"
    script.write_text(_ESCAPEE, encoding="utf-8")
    marker = tmp_path / "kacak.txt"

    started = time.monotonic()
    cap = run([sys.executable, str(script), token, str(marker)], timeout=2.0)
    gecen = time.monotonic() - started

    try:
        assert marker.read_text(encoding="utf-8") == token, "kacak surec hic baslamadi"
        assert cap.meta.timed_out
        assert gecen < 15, f"kosum {gecen:.1f}s surdu -- suresi baskasinin elinde"
        assert cap.meta.byte_count > 0
        assert "basladi" in cap.text(), "zaman asimindan onceki cikti diske inmemis"
    finally:
        for pid in _alive(token):
            with contextlib.suppress(OSError, ValueError):
                os.kill(int(pid), signal.SIGKILL)
