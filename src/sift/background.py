"""Commands left running, and the part of one nobody has read yet.

Everywhere else in this tool a capture is finished before anyone looks at it,
and that is what keeps the rest simple: the bytes do not move while they are
being judged. A command still running breaks that assumption, and this module
is the small amount of bookkeeping that makes it safe to break.

Two decisions do most of the work.

**A look is a slice, not a capture.** Following a running command hands back the
lines that arrived since the last look, and those lines keep the numbers they
have in the whole capture -- line 812 is line 812 in `sift peek`, not line 1 of
some second file. Copying each slice into a capture of its own would have been
easier to write, and would have doubled the bytes on disk, filled `sift list`
with fragments of a single run, and made `sift stats` count one command four
times.

**The cursor is a file, not a variable.** Every `sift` invocation is its own
process. A cursor held in memory starts at zero each time, and the reader is
handed the same thousand lines again -- which is precisely the cost this tool
exists to avoid.

And one rule that keeps a slice honest: a slice ends at the last newline that
has arrived. Whatever comes after it is a line the command is still in the
middle of writing. Showing it now would present half a line as a whole one, and
the other half would arrive later looking like a line of its own -- two lines
in the reader's view that never existed in the output.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from sift import jobs, store
from sift import lines as text_lines

# How long a command gets to end politely before it is ended for it.
GRACE = 5.0

# How often the wait above looks to see whether the ending has been written.
_TICK = 0.1


def launch(
    command: Sequence[str],
    *,
    cwd: str | Path | None = None,
    shell: bool = False,
) -> store.Running:
    """Start a command, leave it running, and write down how to find it again.

    Nothing is waited for. What comes back is the handle to ask about later,
    which is all any other invocation needs: the output reaches the capture file
    as it is produced, and the ending is written by the supervisor.
    """
    argv = list(command)
    started = store.now()
    handle = store.new_handle(argv, started)
    # Created empty here rather than left to the supervisor, which opens it a
    # moment later. Between those two moments the handle exists and its capture
    # does not, and every reader -- `peek`, `follow`, a listing -- would have to
    # answer "no such capture" about a run that had just been started.
    store.begin(handle).touch(exist_ok=True)
    where = str(Path(cwd).resolve()) if cwd else os.getcwd()

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "sift.watch",
            handle,
            repr(started),
            "shell" if shell else "noshell",
            where,
            "--",
            *argv,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        cwd=where,
        **_detached(),
    )

    # Written after the spawn, so the marker cannot outlive a launch that never
    # happened. The cost is a moment where the run exists and `sift list` does
    # not mention it; the supervisor still writes `meta.json` at the end, so
    # even in that unlucky moment nothing is lost, only briefly unlisted.
    running = store.Running(
        handle=handle,
        command=argv,
        shell=shell,
        cwd=where,
        started_at=started,
        pid=proc.pid,
    )
    store.mark_running(running)
    return running


def _detached() -> dict[str, object]:
    """Start the supervisor in a session of its own, and the command inside it.

    Two things follow, both of them wanted. The supervisor outlives the shell
    that launched it, so closing the terminal does not end the run. And the
    command, started by the supervisor without a session of its own, lands in
    the supervisor's process group -- which is what lets `stop` end a build and
    the four compilers it spawned with a single signal.
    """
    if sys.platform == "win32":
        detached = getattr(subprocess, "DETACHED_PROCESS", 0)
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | detached}
    return {"start_new_session": True}


def ours(running: store.Running) -> bool:
    """Whether that pid is still the supervisor this run started, or a stranger.

    This is the most important check in the module, and it was learned the
    expensive way. A pid is a number the operating system hands out again.
    `running.json` outlives the process it names -- a supervisor killed hard
    never gets to remove it -- so by the time anyone reads that number it may
    belong to something else entirely, or to nothing that was ever ours. And
    `stop` does not signal a process, it signals a whole **group**. Believing a
    stale number there is not a failed stop, it is a signal delivered to
    strangers -- and when the number is 1 it is worse than that. `os.killpg(g,
    s)` is `kill(-g, s)`, and `kill(-1, ...)` does not mean "process group 1":
    POSIX gives it to *every process the caller may signal*, init excepted.
    Measured here on 2026-09-08: `kill(1, 0)` is refused, because init is root,
    while `killpg(1, 0)` succeeds -- the caller can always signal itself. So a
    marker naming pid 1 does not end somebody else's build. It ends the
    terminal, the shell that started it, and this process.

    The test is that the pid is still a group leader. `launch` starts the
    supervisor in a session of its own, so for as long as it lives its group id
    equals its process id, and nothing that merely inherited the number has that
    property by accident. pid 1 is refused outright: it satisfies the test, it
    is never ours, and its group is where everything else ends up.
    """
    if running.pid <= 1:
        return False
    if _unreaped(running.pid):
        return False
    if sys.platform == "win32":
        # No process groups in this sense, so there is nothing to compare and
        # nothing to widen a signal into: only the named process is ever hit.
        return True
    try:
        return os.getpgid(running.pid) == running.pid
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _running_on_windows(pid: int) -> bool:
    """Whether that process is still there, without ending it to find out.

    `os.kill(pid, 0)` is a question on POSIX and an execution on Windows. There,
    every signal except `CTRL_C_EVENT` and `CTRL_BREAK_EVENT` is turned into
    `TerminateProcess`, with the signal number used as the exit code -- so the
    probe that costs nothing everywhere else would have `sift list` killing the
    runs it was asked to list, and `follow` ending the build it was asked to
    report on.

    Measured on windows-latest: `stop` was followed by `alive` returning True,
    because the probe and the kill are the same call there and the order of
    events stopped meaning anything.

    So the question is asked the way Windows asks it: open a handle with the
    right to wait on it, and see whether the wait would return at once. A
    process that has exited is signalled; one still running is not, and the wait
    times out immediately because it was given no time.
    """
    import ctypes

    SYNCHRONIZE = 0x0010_0000
    WAIT_TIMEOUT = 0x0000_0102

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return False  # gone, or never ours to look at
    try:
        return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
    finally:
        kernel32.CloseHandle(handle)


def _unreaped(pid: int) -> bool:
    """A process that has exited and has not yet been collected by its parent.

    A zombie keeps its pid, keeps its process group, and still answers signal 0.
    To every other check here it is indistinguishable from a healthy process,
    and it is watching nothing at all.

    This only arises for a caller that launched the supervisor and then stayed
    alive -- a long-running server, or a test -- and that is exactly the case
    worth getting right: a supervisor killed hard leaves no `meta.json`, so
    without this the run would read `running` for the rest of that process's
    life, which is the one state this design exists to be able to deny.

    Read from `/proc` where there is one, and skipped where there is not. The
    command name sits in brackets and may itself contain spaces and brackets, so
    the state letter is found from the last closing bracket rather than by
    splitting fields from the left.
    """
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            stat = f.read()
    except OSError:
        return False
    cut = stat.rfind(b")")
    return cut > 0 and stat[cut + 1 :].strip()[:1] == b"Z"


def alive(running: store.Running) -> bool:
    """Whether the supervisor of this run is still there.

    Asked about the supervisor rather than about the command, because the
    supervisor is what will write the ending. If it is gone and no `meta.json`
    was written then the run did not finish, it was lost, and a reader is far
    better told that than left waiting for an ending nobody will write.

    A pid that is not ours is not alive for this purpose, however healthy the
    process wearing that number is -- see `ours`. Past that, signal 0 asks the
    question without answering it: it checks the process exists and that we may
    signal it, and delivers nothing.

    On Windows it delivers a great deal, which is why that platform is answered
    somewhere else -- see `_running_on_windows`.
    """
    if not ours(running):
        return False
    if sys.platform == "win32":
        return _running_on_windows(running.pid)
    try:
        os.kill(running.pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # it is there; it is simply not ours to signal
    except OSError:
        return False
    return True


def unread(handle: str) -> tuple[list[str], int, store.Cursor]:
    """The new lines, the number the first of them has, and where they leave the reader.

    The number comes back rather than being worked out by the caller, because
    working it out means adding one to a count of lines already read, and a
    caller that gets that wrong produces a view whose numbers are all off by one
    -- correct-looking, and pointing at the wrong line of the capture.

    The cursor comes back rather than being saved. Saving it here would mark
    those lines as read before anything had been done with them, and a view that
    then failed to build would take them with it -- output the reader never saw
    and can no longer ask for.
    """
    cursor = store.load_cursor(handle)
    first = cursor.lines + 1
    path = store.raw_path(handle)
    if not path.is_file():
        return [], first, cursor
    try:
        with open(path, "rb") as source:
            source.seek(cursor.bytes)
            fresh = source.read()
    except OSError:
        return [], first, cursor

    cut = fresh.rfind(b"\n")
    if cut < 0:
        # Nothing but the line being written right now. It will be a whole line
        # soon enough, and a whole line is the smallest thing worth showing.
        return [], first, cursor

    # Cutting at a newline also settles the decoding: a newline byte can never
    # be part of a multi-byte character, so this slice is a whole number of
    # characters and no character is split between two looks.
    whole = fresh[: cut + 1]
    found = text_lines.of(whole.decode("utf-8", errors="replace"))
    moved = store.Cursor(bytes=cursor.bytes + len(whole), lines=cursor.lines + len(found))
    return found, first, moved


def wait_for(handle: str, seconds: float) -> bool:
    """Wait until this run has said something new, or until the time is up.

    Returns whether anything arrived. Without this a caller watching a build has
    only one move: ask, get nothing, sleep, ask again. Every one of those empty
    asks is a tool result that stays in the conversation for the rest of it --
    the exact cost this project exists to avoid, paid to find out that nothing
    happened.

    A run that has already finished is not waited for. There is nothing else
    coming, and a caller told to wait ten seconds for a command that ended an
    hour ago has been given the worst of both.
    """
    deadline = store.now() + max(0.0, seconds)
    while True:
        if unread(handle)[0]:
            return True
        running = store.load_running(handle)
        if running is None or not alive(running):
            return False
        if store.now() >= deadline:
            return False
        time.sleep(_TICK)


def seen(handle: str, cursor: store.Cursor) -> None:
    """Mark everything up to `cursor` as handed over."""
    store.save_cursor(handle, cursor)


def stop(handle: str) -> store.Meta | None:
    """End a running command, and make sure the run ends up with an ending.

    Returns what the run came to, or None for a handle that was never used. A
    command that had already finished is left exactly as it was: stopping
    something that has stopped is not an error, and rewriting its ending would
    replace a real exit code with a guess.
    """
    running = store.load_running(handle)
    if running is None:
        return store.load(handle)

    sent = _end(running)
    settled = _settled(handle)
    if settled is not None:
        return settled

    # The supervisor never got to write the ending: killed harder than it could
    # survive, or already gone before this was asked. Somebody has to write one,
    # or the handle stays marked running for as long as its directory exists.
    return _close(running, sent)


def _end(running: store.Running) -> int | None:
    """Ask the tree to stop, then insist. Returns the last signal actually sent.

    SIGTERM first, because a command that can tidy up deserves the chance: a
    test runner shot mid-write leaves a broken file behind. SIGKILL after,
    because "asked politely" is not a way to end a run -- a process that ignores
    TERM would otherwise keep the handle marked running forever.

    The signal goes to the group rather than to the process. The supervisor and
    the command share one, along with everything the command started.

    Windows has no such group, so the tree lives in a job object instead and
    ending that is what reaches the command's children. The supervisor is
    deliberately left outside the job: it survives this, watches the command go,
    and writes the ending itself. Signalling it instead would be worse than
    useless there -- `SIGTERM` on Windows is `TerminateProcess`, so the one
    process that could record how the run came out would be killed before it
    could, which is exactly what used to happen.
    """
    if not alive(running):
        return None

    # False everywhere but Windows, and on Windows for a run started before jobs
    # existed. Either way the line below is what happens instead.
    if not jobs.end(running.handle):
        _signal(running.pid, signal.SIGTERM)  # to the group: `ours` vouched for it
    deadline = store.now() + GRACE
    while store.now() < deadline:
        if store.meta_path(running.handle).is_file():
            return signal.SIGTERM
        time.sleep(_TICK)

    hard = getattr(signal, "SIGKILL", signal.SIGTERM)
    _signal(running.pid, hard)
    return hard


def _signal(pid: int, number: int) -> None:
    """Send one signal to a whole tree, or to as much of it as the system allows.

    The first line is a floor, and it is deliberately a second copy of a rule
    `ours` already keeps. Two guards for one rule is not duplication here, it is
    the point: `ours` is a single line, a single edit removes it, and what is on
    the other side of that line is not a wrong process ended, it is `kill(-1)` --
    every process this user owns. One guard means one edit away from that.

    A pid of 0 is the same mistake with a smaller blast radius and no warning at
    all: `getpgid(0)` answers with the *caller's* group, so a marker naming 0
    would end the run that was doing the stopping.

    Neither is a tree to end. Nothing this tool starts has a pid below 2, so
    refusing them costs nothing that was ever wanted, and the group is refused
    on the same grounds for the same reason.
    """
    if pid <= 1:
        return

    try:
        if sys.platform == "win32":
            # The job has already ended the tree if there was one; this ends the
            # supervisor, which is not in it. A run started before jobs existed,
            # or one whose supervisor is gone, has no job -- and then this line
            # is the whole of what Windows can do, as it always was.
            os.kill(pid, number)
        else:
            group = os.getpgid(pid)
            if group > 1:
                os.killpg(group, number)
            else:
                os.kill(pid, number)
    except (ProcessLookupError, PermissionError, OSError):
        with contextlib.suppress(OSError):
            os.kill(pid, number)


def _settled(handle: str, wait: float = 1.0) -> store.Meta | None:
    """Give the supervisor a moment to write the ending it is better placed to write."""
    deadline = store.now() + wait
    while True:
        meta = store.load(handle)
        if meta is not None:
            return meta
        if store.now() >= deadline:
            return None
        time.sleep(_TICK)


def _close(running: store.Running, sent: int | None) -> store.Meta:
    """Write the ending the supervisor did not get to write.

    A command killed by a signal is recorded the way the operating system would
    have reported it -- a negative exit code naming the signal -- because that
    is what happened, and because it is what `Meta.failed` already knows how to
    read. When nothing was sent, nothing is claimed: the exit code is left empty
    to say that this run's ending is genuinely not known.
    """
    target = store.raw_path(running.handle)
    meta = store.Meta(
        handle=running.handle,
        command=list(running.command),
        shell=running.shell,
        exit_code=None if sent is None else -int(sent),
        timed_out=False,
        started_at=running.started_at,
        duration_s=round(store.now() - running.started_at, 3),
        byte_count=target.stat().st_size if target.is_file() else 0,
        cwd=running.cwd,
    )
    store.finish(meta)
    store.clear_running(running.handle)
    return meta
