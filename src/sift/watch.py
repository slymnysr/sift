"""The process that stays behind when a command is left running.

`sift run` waits for the command and then hands back a view. `sift run
--background` cannot: the point of it is that the caller gets their prompt back.
Something still has to be there when the command ends, because the one thing a
capture cannot be asked afterwards is how it ended. A process that has already
exited does not tell a stranger its exit code.

So the launcher starts this, and this starts the command. It is the smallest
program that can honestly close a run: it waits, then writes `meta.json`. No
model, no network, no judgement -- those happen later, in whichever process
asks to see the output.

The command's bytes go straight to the capture file and not through here. That
is worth saying out loud: if this process is killed, the output keeps arriving.
What is lost is the ending, which is why `background.stop` is prepared to write
one itself.

Stopping works because of where this sits. The launcher puts it in a session of
its own and the command, started without one, joins its group -- so ending the
group ends both, a build and the four compilers it spawned included. A SIGTERM
arriving here is passed on rather than taken personally, so a stopped run still
gets a `meta.json` instead of looking, forever, like something still going.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys

from sift import store

_USAGE = "usage: python -m sift.watch <handle> <started_at> <shell|noshell> <cwd> -- command..."

# What a command that could not be started is reported as. It is what a shell
# reports for the same failure, so a command that does not exist ends the same
# way whether or not `shell=True` was asked for.
_CANNOT_START = 127


def main(argv: list[str] | None = None) -> int:
    """Wait for one command and write down how it ended.

    The whole plan arrives in argv rather than through a file. Both would work,
    but argv arrives with the process: there is no moment where this is running
    and does not yet know what it is watching, and nothing left behind to clean
    up if the launcher dies between writing the plan and spawning this.
    """
    words = list(sys.argv[1:] if argv is None else argv)
    if len(words) < 6 or words[4] != "--":
        print(_USAGE, file=sys.stderr)
        return 2
    handle, when, how, cwd = words[:4]
    try:
        started_at = float(when)
    except ValueError:
        print(_USAGE, file=sys.stderr)
        return 2
    return watch(handle, words[5:], started_at=started_at, shell=how == "shell", cwd=cwd)


def watch(
    handle: str,
    command: list[str],
    *,
    started_at: float,
    shell: bool = False,
    cwd: str = "",
) -> int:
    """Run the command, then record the ending nobody was there to see."""
    target = store.begin(handle)

    # Opened for appending, not writing: append is the mode that survives two
    # writers and a restart. The command inherits this handle and does its own
    # writing through it, so the bytes land whether or not this process is still
    # alive to care.
    sink = open(target, "ab")  # noqa: SIM115 -- the command writes through this; closed below
    try:
        proc = subprocess.Popen(
            " ".join(command) if shell else command,
            stdout=sink,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            cwd=cwd or None,
            shell=shell,
        )
    except OSError:
        # Nobody to raise at. This process is the only one that knows the
        # command never started, and a handle left marked running is worse than
        # a handle marked failed.
        sink.close()
        _record(handle, command, shell, cwd, started_at, _CANNOT_START)
        return _CANNOT_START

    with sink:
        exit_code = _wait(proc)
    _record(handle, command, shell, cwd, started_at, exit_code)
    return exit_code


def _wait(proc: subprocess.Popen) -> int:
    """Wait for the command, passing on any request to stop rather than dying of it.

    A supervisor that took SIGTERM personally would leave the command running
    with nothing watching it and no `meta.json` ever written: the run would look
    busy for as long as its directory survives. So the signal is forwarded and
    the wait goes on. Whatever the command decides to do about it, this process
    is still here afterwards to write down what happened.

    Forwarding is belt and braces -- a signal sent to the group has already
    reached the command -- and it is what makes `kill <pid>` by hand behave the
    same as `sift stop`.
    """

    def relay(number, _frame):
        with contextlib.suppress(OSError, ProcessLookupError):
            proc.send_signal(number)

    for name in ("SIGTERM", "SIGINT", "SIGHUP"):
        number = getattr(signal, name, None)
        if number is not None:
            with contextlib.suppress(OSError, ValueError):
                signal.signal(number, relay)

    return proc.wait()


def _record(
    handle: str,
    command: list[str],
    shell: bool,
    cwd: str,
    started_at: float,
    exit_code: int,
) -> None:
    """Close the run: write the ending first, then take down the marker.

    In that order, and the order is the whole point. A reader that arrives
    between the two sees a capture that is finished and still marked running,
    which `store.load_running` already answers correctly -- `meta.json` wins.
    The other order has no such answer: for that moment the run is neither
    running nor finished, and a caller waiting on it is told there is nothing
    left to wait for.
    """
    target = store.raw_path(handle)
    store.finish(
        store.Meta(
            handle=handle,
            command=list(command),
            shell=shell,
            exit_code=exit_code,
            timed_out=False,
            started_at=started_at,
            duration_s=round(store.now() - started_at, 3),
            byte_count=target.stat().st_size if target.is_file() else 0,
            cwd=cwd or os.getcwd(),
        )
    )
    store.clear_running(handle)


if __name__ == "__main__":  # pragma: no cover -- the entry point itself
    raise SystemExit(main())
