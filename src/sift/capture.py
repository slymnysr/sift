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

from sift import store

_READ_CHUNK = 64 * 1024
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

    sink = open(target, "wb")  # noqa: SIM115 -- the pump closes this; see below
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
        _stop(proc)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=5)
        exit_code = None
    finally:
        stop.set()
        pump.join(timeout=_DRAIN_GRACE)

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
    )
    store.finish(meta)
    return Capture(meta)


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


def _stop(proc: subprocess.Popen) -> None:
    """End a run that overstayed, the whole tree of it where the platform allows."""
    try:
        if sys.platform == "win32":
            proc.kill()
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        with contextlib.suppress(OSError):
            proc.kill()
