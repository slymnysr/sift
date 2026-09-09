"""Ending a whole tree on Windows, where there are no process groups.

Everywhere else, a run is put in a session of its own and one `killpg` ends the
command and everything it started. Windows has no equivalent, and until this
existed `sift stop` there ended the process named on the command line and left
its children running -- a build's four compilers, a test runner's workers --
writing into a file nobody was reading. The README promised otherwise.

A job object is what Windows has instead. Processes are put in one, the job is
terminated, and everything in it goes with it. Two details make it usable from
here:

*The job is named.* `sift stop` runs minutes later, in a different process, and
a handle cannot be posted between them. A name can: the run's own handle becomes
`Local\\sift-<handle>`, which the stopper opens by name.

*The job does not kill on close.* Windows will end everything in a job the
moment the last handle to it goes away, and that is not wanted here. A
supervisor that is killed leaves its command running on purpose -- the bytes
keep arriving and `stop` is prepared to write the ending itself. Turning that
on would make Windows the one platform where killing the watcher kills the work.

Nothing here raises. Every function answers with a bool, because the caller's
job is to end a run and a system call that would not cooperate is not a reason
to stop trying the other ways.
"""

from __future__ import annotations

import sys

# Rights asked for when opening someone else's job or process. Named rather than
# spelled in place, because a wrong constant here is a call that fails with a
# number instead of doing the wrong thing loudly.
_JOB_TERMINATE = 0x0008
_PROCESS_SET_QUOTA = 0x0100
_PROCESS_TERMINATE = 0x0001


def named(handle: str) -> str:
    """What the job for one run is called.

    `Local\\` keeps it in the session, which is where every process this tool
    starts lives. A global name would be visible to other logged-in users and
    there is nothing here worth showing them.
    """
    return f"Local\\sift-{handle}"


def usable() -> bool:
    """Whether this platform has job objects at all."""
    return sys.platform == "win32"


def hold(handle: str):
    """Make the named job for a run, or return nothing if it cannot be made.

    The caller keeps what comes back for as long as the run lasts: a job object
    exists while a handle to it is open, and one nobody holds is a name that
    `stop` will look for and not find.
    """
    if not usable():
        return None
    import ctypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = ctypes.c_void_p
    job = kernel.CreateJobObjectW(None, named(handle))
    return job or None


def joined(job, pid: int) -> bool:
    """Put a process, and so everything it starts, into the job."""
    if job is None or not usable() or pid <= 1:
        return False
    import ctypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    process = kernel.OpenProcess(
        _PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, ctypes.c_ulong(pid)
    )
    if not process:
        return False
    try:
        return bool(
            kernel.AssignProcessToJobObject(ctypes.c_void_p(job), ctypes.c_void_p(process))
        )
    finally:
        kernel.CloseHandle(ctypes.c_void_p(process))


def end(handle: str) -> bool:
    """End everything in a run's job. False when there is no such job.

    False is an ordinary answer and not a failure: a run started before this
    existed, or one whose supervisor has already gone, has no job to open. The
    caller falls back to ending the process it knows about, which is what this
    tool did on Windows for its whole life until now.
    """
    if not usable():
        return False
    import ctypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenJobObjectW.restype = ctypes.c_void_p
    job = kernel.OpenJobObjectW(_JOB_TERMINATE, False, named(handle))
    if not job:
        return False
    try:
        return bool(kernel.TerminateJobObject(ctypes.c_void_p(job), ctypes.c_uint(1)))
    finally:
        kernel.CloseHandle(ctypes.c_void_p(job))


def close(job) -> None:
    """Let go of a job. What is in it keeps running; only the name goes away."""
    if job is None or not usable():
        return
    import ctypes

    ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(ctypes.c_void_p(job))
