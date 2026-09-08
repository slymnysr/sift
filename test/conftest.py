"""Undo a mutation an earlier run was killed in the middle of, before anything runs.

`mutations.py` writes a rule-breaking edit into a source file, runs the suite,
and puts the file back in a `finally`. That covers everything except the case
this file exists for: the process not being asked politely -- a SIGKILL, a
machine that reboots, a session that takes its children with it.

The battery already knew how to repair that. `undo_leftover` compares the file
byte for byte against what was written, restores the original, and clears the
note. The gap was never the repair, it was *when it ran*: only from the
battery's own `main`. And what people run is `pytest`.

So a break left on disk survived every ordinary test run. Measured, on this
machine, on 2026-09-08: the leftover mutation was the one that disables the
guard in `background.ours` -- the rule that a pid this tool did not start is
never signalled. `pytest` then reached the test that writes a marker naming pid
1, the assertion caught the mutation and stopped the test before its own
cleanup, and the teardown swept the marker with `background.stop`. That signals
a process *group*: `killpg(1)` took down the terminal multiplexer, the session
running the tests, and the WSL distribution with them. The suite never got to
report anything, the `finally` never ran, and the mutation was still on disk
for the next run to do it again -- six times in one evening, each one looking
like an unexplained disconnection rather than a test result.

A repair that only runs when somebody remembers to ask for it is not a repair.
This runs before collection, on every invocation, and says what it undid.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mutations import MUTATING, undo_leftover


def pytest_configure(config: object) -> None:
    """Repair first, collect second. Nothing here fails a run.

    Except when the battery is the one running us. `mutations.py` breaks a rule
    on purpose and runs this suite to watch it be caught, and from in here that
    is byte for byte the situation this file exists to repair -- a note on disk
    and a source file that matches it. Undoing it would revert the mutation
    before a single test saw it, every mutation would come back green, and the
    battery would report that nothing catches anything. A safety net that
    silently turns the measurement off is worse than no safety net, because the
    number it leaves behind still looks like a measurement.

    So the battery says so, in the environment, and this stands aside. Its
    `finally` is the right repair while it is alive; this one is for when it is
    not.

    Everything else is caught and shrugged off. An unreadable note, a file
    somebody has edited since, a repair that does not apply -- each means *this
    is not the situation it was left here for*, and the answer is to carry on
    and let the suite say what it finds. A conftest that raises reports nothing.
    """
    if os.environ.get(MUTATING):
        return
    try:
        undone = undo_leftover()
    except Exception as exc:  # a repair must not cost the caller their test run
        print(f"conftest: could not check for a leftover mutation ({exc})")
        return
    if undone is not None:
        print(f"conftest: undid a mutation an earlier run left behind -- {undone}")
