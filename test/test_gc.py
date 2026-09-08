"""Faz 21 -- the only thing here that deletes anything.

Two claims are defended, and the second is the harder one. That `gc` removes
what it says it removes, and that **nothing else does** -- no age, no ceiling,
no tidy-up on the way past. The second rule of this project is that nothing is
thrown away, and a command somebody types is the one act that is allowed to be
an exception to it.
"""

from __future__ import annotations

import json

import pytest

from sift import capture, cli, peek, store

DAY = 86_400.0


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    for name in ("SIFT_API_KEY", "NVIDIA_API_KEY", "SIFT_KEEP_DAYS"):
        monkeypatch.delenv(name, raising=False)


def _capture(command: str = "one") -> str:
    """A finished capture of a real command, with its own handle."""
    return capture.run(["python3", "-c", f"print({command!r})"]).handle


def _age(handle: str, days: float) -> None:
    """Move a capture's ending that far into the past, in its own record."""
    p = store.meta_path(handle)
    data = json.loads(p.read_text(encoding="utf-8"))
    data["started_at"] = store.now() - days * DAY - data.get("duration_s", 0.0)
    p.write_text(json.dumps(data), encoding="utf-8")


def test_an_old_capture_goes_and_a_young_one_stays():
    old, young = _capture("old"), _capture("young")
    _age(old, days=40)

    swept = store.sweep(30 * DAY)

    assert [one.handle for one in swept] == [old]
    assert store.load(old) is None
    assert store.load(young) is not None
    assert store.read_raw(young)


def test_a_run_still_going_is_never_swept():
    """It is being written to, and nobody knows yet how it came out. Age is not
    the question for a capture that is not finished."""
    handle = _capture("going")
    _age(handle, days=400)
    store.mark_running(
        store.Running(
            handle=handle,
            command=["sleep", "3600"],
            shell=False,
            cwd="/tmp",
            started_at=store.now(),
            pid=999_999,
        )
    )

    assert store.sweep(1.0) == []
    assert store.load(handle) is not None


def test_a_capture_whose_age_cannot_be_established_is_left_alone():
    """No `meta.json` and no bytes is no evidence, and deleting on no evidence
    is deleting on a guess."""
    store.captures_dir().joinpath("deadbeef").mkdir(parents=True)

    assert store.sweep(0.0) == []
    assert store.captures_dir().joinpath("deadbeef").is_dir()


def test_what_went_is_named_while_it_can_still_be_read():
    handle = _capture("named")
    _age(handle, days=40)

    swept = store.sweep(30 * DAY)

    assert swept[0].command[0] == "python3"
    assert swept[0].byte_count > 0


def test_the_directory_goes_and_one_line_is_kept():
    """The stone is one line in one file, not a directory each.

    A directory per removed capture is four kilobytes of block to hold fifty-two
    bytes, kept for as long as the store lives -- a sweep that reclaims space by
    leaving a permanent tax on having had it.
    """
    handle = _capture("gone")
    _age(handle, days=40)

    store.sweep(30 * DAY)

    assert not store.captures_dir().joinpath(handle).exists()
    stone = store.gone(handle)
    assert stone is not None
    assert stone.byte_count > 0
    # A date and a size. Not the command: that is the most identifying part of
    # what was just deleted, and keeping it would undo the deletion by half.
    written = store.gone_path().read_text(encoding="utf-8")
    assert handle in written
    assert "python3" not in written


def test_a_handle_that_was_swept_answers_differently_from_one_that_never_was():
    """The whole reason a stone is kept at all. A gap marker printed a fortnight
    ago sends someone to `sift peek 9f2c41ab`, and "removed on the 8th" and
    "there is no such thing" are not the same answer."""
    handle = _capture("asked about later")
    _age(handle, days=40)
    store.sweep(30 * DAY)

    with pytest.raises(FileNotFoundError) as swept:
        peek.bytes_of(handle)
    with pytest.raises(FileNotFoundError) as invented:
        peek.bytes_of("ffffffff")

    assert "removed by sift gc" in str(swept.value)
    assert "removed by sift gc" not in str(invented.value)


def test_sweeping_twice_removes_nothing_the_second_time():
    handle = _capture("once")
    _age(handle, days=40)

    assert len(store.sweep(30 * DAY)) == 1
    assert store.sweep(30 * DAY) == []
    assert store.gone(handle) is not None


def test_how_old_is_old_can_be_said_in_the_environment(monkeypatch):
    assert store.keep_days() == float(store.KEEP_DAYS)
    monkeypatch.setenv("SIFT_KEEP_DAYS", "7")
    assert store.keep_days() == 7.0
    monkeypatch.setenv("SIFT_KEEP_DAYS", "not a number")
    assert store.keep_days() == float(store.KEEP_DAYS)
    monkeypatch.setenv("SIFT_KEEP_DAYS", "-3")
    assert store.keep_days() == float(store.KEEP_DAYS)


def test_running_a_command_sweeps_nothing():
    """The rule this phase is mostly about. Every other command here can be run
    without thinking about it because none of them destroy anything, and that
    stays true now that one of them can."""
    old = _capture("old enough to go")
    _age(old, days=4000)

    assert cli.main(["run", "--", "python3", "-c", "print('hello')"]) == 0
    assert cli.main(["list"]) == 0
    assert cli.main(["stats"]) == 0

    assert store.load(old) is not None, "something swept without being asked to"


def test_the_command_line_says_what_went_and_what_it_freed(capsys):
    handle = _capture("printed")
    _age(handle, days=40)

    assert cli.main(["gc", "30"]) == 0

    said = capsys.readouterr().out
    assert handle in said
    assert "1 capture removed" in said
    assert "freed" in said


def test_the_command_line_says_so_when_there_is_nothing_to_remove(capsys):
    _capture("too young")
    assert cli.main(["gc"]) == 0
    assert "nothing here is older" in capsys.readouterr().out


def test_a_gc_that_was_asked_in_words_rather_than_days_is_refused(capsys):
    _capture("kept")
    assert cli.main(["gc", "yesterday"]) == 2
    assert "number of days" in capsys.readouterr().err
