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

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mutations import MUTATING, undo_leftover


@pytest.fixture(autouse=True)
def _own_store(tmp_path, monkeypatch):
    """No test writes into the store somebody actually uses.

    Most test files set this themselves and always did. `test_lines.py` did not,
    because it is about where a line ends and looks like it touches nothing --
    and it runs real commands to find out, and every one of them landed in
    `~/.cache/sift`. Measured: 516 captures, from two files, accumulated there
    across this project's own test runs, and nobody noticed because they are
    seventeen bytes each and nothing ever lists them.

    That is the shape of the bug worth guarding against rather than fixing once:
    it is not that a file forgot, it is that forgetting was possible and silent.
    So the isolation stops being something each file remembers and becomes
    something none of them can opt out of. A file that sets `SIFT_HOME` again
    for its own reasons still wins; it just no longer has to.
    """
    monkeypatch.setenv("SIFT_HOME", str(tmp_path / "sift"))
    # And no test is answered out of the cache unless it says so.
    #
    # Almost everything here measures what happens when the question is asked:
    # what was in the prompt, how many asks it took, what a fallback does when
    # the model cannot be reached. A cache that quietly answers instead turns
    # those into measurements of nothing, and it does it without failing --
    # `test_the_name_of_a_file_plays_no_part_in_its_outline` outlines the same
    # bytes under two names, and with the cache on the second one never reaches
    # a model at all, so the thing it exists to compare does not happen.
    #
    # `test_answers.py` turns it back on, which is the right shape: the cache is
    # a feature with its own tests rather than a condition every other test is
    # silently run under.
    monkeypatch.setenv("SIFT_CACHE", "0")


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
