"""Running the command, and keeping every byte of what it said.

`sift` runs the command itself rather than being handed its output afterwards.
That is not a convenience: it is what makes the rest possible. Output that has
already reached the conversation has already been paid for, and no amount of
distilling afterwards refunds it. Standing where the bytes appear is the only
place a tool can act before the cost is incurred.

Two choices here are worth stating, because both could reasonably have gone the
other way.

**stderr is merged into stdout.** Kept apart, the two streams have to be stitched
back together afterwards and the order is guesswork; merged at the pipe, the
operating system interleaves them exactly as a terminal would. What a person
would have seen is the thing worth judging, so that is what gets stored.

**Bytes go straight to disk.** A command that prints for an hour must not grow
the process that is watching it. The file is the buffer, and reading back for
judgement is bounded separately -- so a runaway `yes` costs disk, which is cheap
and reclaimable, rather than memory, which is neither.
"""

from __future__ import annotations

import contextlib
import os
import selectors
import signal
import subprocess
import sys
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from sift import jobs, store

_READ_CHUNK = 64 * 1024

# How much of one command's output is kept before keeping stops.
#
# The second rule says nothing is thrown away, and this does not throw anything
# away: what was written stays written and every line of it is still there to
# `peek`. What it refuses is the other failure, which the second rule was never
# meant to license -- a command in a loop writing until the disk is full, on a
# machine somebody else needs.
#
# A gigabyte is far past any real build log and reached in seconds by `yes`.
# `SIFT_MAX_CAPTURE` is in bytes, and 0 means no ceiling at all for anyone who
# would rather have the disk.
_MAX_CAPTURE = 1024 * 1024 * 1024


def ceiling() -> int:
    """How many bytes one capture may keep, or 0 for no limit."""
    written = (os.environ.get("SIFT_MAX_CAPTURE") or "").strip()
    if not written:
        return _MAX_CAPTURE
    try:
        asked = int(written)
    except ValueError:
        return _MAX_CAPTURE
    return max(asked, 0)
_TICK = 0.1  # how often a waiting pump looks up to see whether it has been told to stop
_DRAIN_GRACE = 2.0  # how long a stopped pump may keep collecting before `run` moves on


@dataclass(frozen=True)
class Capture:
    """One finished run: how it ended, and where its bytes are."""

    meta: store.Meta

    @property
    def handle(self) -> str:
        return self.meta.handle

    @property
    def raw(self) -> bytes:
        return store.read_raw(self.handle)

    def text(self) -> str:
        """The capture as text.

        Decoded with replacement rather than strictness, because a build log is
        allowed to contain a stray byte and a tool that raises on it would be
        useless exactly when it is needed. Size is measured after this point:
        one invalid byte becomes a three-byte replacement character, so counting
        before decoding would understate what a model is about to be shown.
        """
        return self.raw.decode("utf-8", errors="replace")


def run(
    command: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    shell: bool = False,
    stdin: bytes | None = None,
) -> Capture:
    """Run a command, store everything it writes, and report how it ended.

    `shell=True` exists because pipes and globs are half of what people actually
    run, and refusing them would only push users back to the unwatched terminal.
    It is opt-in and never the default: a list of arguments cannot be
    accidentally reinterpreted by a shell, and that is the safer thing to reach
    for first.
    """
    argv = list(command)
    started = store.now()
    handle = store.new_handle(argv, started)
    target = store.begin(handle)

    popen_command: Sequence[str] | str = " ".join(argv) if shell else argv
    timed_out = False
    exit_code: int | None = None
    # Made before the command starts, so nothing it spawns in its first
    # milliseconds is outside it. None everywhere but Windows, where it is the
    # only thing a timeout can use to reach the command's children.
    job = jobs.hold(handle)

    sink = _Sink(
        open(target, "wb"),  # noqa: SIM115 -- the pump closes this; see below
        ceiling(),
    )
    try:
        # Running whatever was asked for is the whole point of this tool, so the
        # usual warning about handing a command to the system does not apply here.
        proc = subprocess.Popen(
            popen_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
            cwd=str(cwd) if cwd else None,
            env=env,
            shell=shell,
            **_new_session(),
        )
    except BaseException:
        sink.close()
        raise

    # Into the job, so that a timeout reaches what the command starts and not
    # only the command. Nothing on POSIX: the session does this work there.
    jobs.joined(job, proc.pid)

    if stdin is not None and proc.stdin is not None:
        with contextlib.suppress(OSError):
            proc.stdin.write(stdin)
        proc.stdin.close()

    # The pump runs on its own thread and the clock is watched here. Reading and
    # timing on one thread cannot both work: a read waits until the pipe has
    # something to give, so a command that prints nothing and never exits -- the
    # exact thing a timeout is for -- would never reach the check.
    #
    # From this point the pump owns the pipe and the file, and closes both when
    # it is finished. Closing either from here would mean closing it out from
    # under a thread that is reading, which is how a bounded wait quietly becomes
    # an unbounded one.
    stop = threading.Event()
    pump = threading.Thread(target=_pump, args=(proc.stdout, sink, stop), daemon=True)
    pump.start()
    try:
        exit_code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _stop(proc, handle)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=5)
        exit_code = None
    finally:
        stop.set()
        pump.join(timeout=_DRAIN_GRACE)
        jobs.close(job)

    meta = store.Meta(
        handle=handle,
        command=argv,
        shell=shell,
        exit_code=exit_code,
        timed_out=timed_out,
        started_at=started,
        duration_s=round(store.now() - started, 3),
        byte_count=target.stat().st_size if target.is_file() else 0,
        cwd=str(Path(cwd).resolve()) if cwd else os.getcwd(),
        capped=sink.capped,
    )
    store.finish(meta)
    return Capture(meta)


def keep(source: BinaryIO, name: str = "-") -> Capture:
    """Store what arrives on a stream, and hand it back as a capture.

    A pipe is the other way somebody else's output reaches this tool. `sift run`
    is for output this process caused; this is for output that was already on
    its way -- `journalctl | sift digest -`, a log a colleague sent through a
    terminal, a build running under something that is not sift.

    It is a capture and not a temporary file because of the second rule.
    Everything a view leaves out has to stay somewhere a `peek` can reach, and a
    scratch file deleted at exit would make the gap marker a promise that is
    already broken by the time it is read.

    Reading is chunked. What arrives on a pipe has no length and no manners: it
    can be four bytes or four gigabytes, and holding it in memory to find out
    which would be a way of losing the whole thing.
    """
    started = store.now()
    handle = store.new_handle([name, str(started)], started)
    target = store.begin(handle)

    kept = _Sink(open(target, "wb"), ceiling())  # noqa: SIM115 -- closed below
    try:
        while True:
            block = source.read(_READ_CHUNK)
            if not block:
                break
            kept.write(block)
    finally:
        kept.close()

    meta = store.Meta(
        handle=handle,
        command=[name],
        shell=False,
        # Nothing was run here, so there is no exit code to report and none is
        # invented. `None` is what the rest of this already means by "the
        # command did not end badly, it did not end at all".
        exit_code=None,
        timed_out=False,
        started_at=started,
        duration_s=round(store.now() - started, 3),
        byte_count=target.stat().st_size if target.is_file() else 0,
        cwd=os.getcwd(),
        capped=kept.capped,
    )
    store.finish(meta)
    return Capture(meta)


class _Sink:
    """A file that stops writing at the ceiling, and remembers that it did.

    Reading does not stop, and that is the whole design. A pipe nobody drains
    fills up, and a command whose pipe is full stops running -- which would be
    this tool changing what the command does, the one thing the third rule
    forbids. So the bytes go on being read; they simply stop being kept.

    Nothing already written is touched. What the ceiling costs is the tail of an
    output that was going to be enormous, and the footer says so rather than
    letting a reader believe they are looking at all of it.
    """

    def __init__(self, target, limit: int) -> None:
        self._file = target
        self._limit = limit  # 0 means no ceiling
        self._written = 0
        self.capped = False

    def write(self, chunk: bytes) -> int:
        if not self._limit:
            return self._file.write(chunk)
        room = self._limit - self._written
        if len(chunk) > room:
            # Everything past the ceiling is dropped here rather than earlier,
            # so that the chunk which straddles it is kept up to the line and no
            # further. Once there is no room at all this writes nothing, which
            # is the same thing said with less code.
            self.capped = True
            chunk = chunk[:room]
        self._written += len(chunk)
        return self._file.write(chunk)

    def close(self) -> None:
        self._file.close()


def _pump(source, sink, stop: threading.Event) -> None:
    """Move bytes from the pipe into the file until the pipe closes, or until
    `stop` is set and there is nothing left to read.

    A pipe stays open while *any* process holds its write end, and the command is
    not always the last one holding it: a build leaves a daemon behind, a test
    runner spawns a worker that steps into its own session. Waiting on a read
    until such a stranger decides to exit is precisely the hang a timeout exists
    to prevent, so the wait here is always a bounded one.

    Nothing is dropped by stopping. A command that has exited already handed its
    bytes to the pipe, so they are readable and get read; the stop only ends the
    waiting for bytes that no longer have an author worth waiting for.

    Errors are swallowed on purpose. This thread exists so the command's output
    is not lost; if the pipe breaks under it, the run is still a real result and
    the bytes written so far are still worth keeping.
    """
    try:
        if sys.platform == "win32":
            _pump_until_closed(source, sink)
        else:
            _pump_until_stopped(source, sink, stop)
    except (OSError, ValueError):
        pass
    finally:
        for closable in (source, sink):
            with contextlib.suppress(OSError, ValueError):
                closable.close()


def _pump_until_stopped(source, sink, stop: threading.Event) -> None:
    """Read only when the pipe says it has something, so waiting stays bounded."""
    fd = source.fileno()
    with selectors.DefaultSelector() as sel:
        sel.register(fd, selectors.EVENT_READ)
        while True:
            if sel.select(timeout=_TICK):
                chunk = os.read(fd, _READ_CHUNK)
                if not chunk:
                    return  # every writer has let go: this is the end of the output
                sink.write(chunk)
            elif stop.is_set():
                return


def _pump_until_closed(source, sink) -> None:
    """The Windows path: wait on the pipe itself.

    Selectors there speak only of sockets, so the read waits until the pipe
    closes. Combined with having no way to kill a process tree, this is the same
    honest limit `_new_session` describes: on Windows a command that leaves
    children behind is watched less closely than on a system with process groups.
    """
    while True:
        chunk = source.read(_READ_CHUNK)
        if not chunk:
            return
        sink.write(chunk)


def _new_session() -> dict[str, object]:
    """Put the child in its own group so a timeout can kill what it started.

    A command that spawns children -- a test runner, a build -- leaves them
    running when only the parent is killed, and those orphans keep writing to a
    pipe nobody is reading. Windows has no process groups in this sense, so
    there the child alone is stopped and that is the honest limit.
    """
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _stop(proc: subprocess.Popen, handle: str) -> None:
    """End a run that overstayed, the whole tree of it.

    Two mechanisms for one sentence. A process group is what POSIX has; a job
    object is what Windows has, and until it was used here a timeout on Windows
    ended the process named on the command line and left its children running --
    writing into a pipe nobody was reading, which is the exact failure the group
    exists to prevent everywhere else.
    """
    try:
        if sys.platform == "win32":
            # Both, and not one instead of the other. The job holds the
            # children; the process named on the command line is ended by name.
            # Treating them as alternatives is how the first version of this
            # ended an empty job, called that success, and left the command
            # running -- which CI found on the first run.
            jobs.end(handle)
            proc.kill()
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        with contextlib.suppress(OSError):
            proc.kill()
