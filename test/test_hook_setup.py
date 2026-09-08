"""Faz 25 -- offering the thing that pays most, and writing into somebody else's file.

`sift hook` was the largest saving in the tool and the only part of it that has
to be switched on, and the only place it was written down was a README. A feature
nobody knows about is a feature nobody has.

So it is offered. Two things are defended here and the second is the serious one:
that the notice says what it costs as well as what it gives, and that installing
it cannot damage a settings file this tool does not own. Every merge is a merge
into somebody's working configuration, and the only safe thing to do with a shape
this does not recognise is to refuse it.
"""

from __future__ import annotations

import json

import pytest

from sift import cli
from sift import hook as h

MINE = {"type": "command", "command": "sift hook"}
THEIRS = {"type": "command", "command": "python3 bash-guard.py", "timeout": 10}


@pytest.fixture(autouse=True)
def _own_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFT_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.delenv("SIFT_HOOK", raising=False)
    return tmp_path / "settings.json"


def _write(path, settings) -> None:
    path.write_text(json.dumps(settings), encoding="utf-8")


def _read(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_notice_says_what_it_costs_and_not_only_what_it_gives():
    """An offer that lists only the upside is a sales pitch. The two costs here
    are real and one of them can bite: a command that outruns the client's hook
    timeout is run again by the client."""
    said = h.offer()

    assert "run twice" in said
    assert "one model request" in said
    assert "fails open" in said
    assert "SIFT_HOOK=0" in said
    assert "Nothing already in that file is changed" in said


def test_it_is_added_beside_what_is_already_there(_own_settings):
    """The case this was written for. A real settings file already has hooks on
    Bash, and they are somebody's, and they keep working."""
    _write(
        _own_settings,
        {"model": "opus", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [THEIRS]}]}},
    )

    done, _ = h.install()

    assert done
    after = _read(_own_settings)
    assert after["model"] == "opus", "an unrelated setting was touched"
    assert after["hooks"]["PreToolUse"][0]["hooks"] == [THEIRS, MINE]


def test_a_file_that_does_not_exist_yet_is_made():
    done, _ = h.install()

    assert done
    assert h.installed()


def test_asking_twice_adds_it_once(_own_settings):
    h.install()
    done, said = h.install()

    assert done
    assert "already" in said
    entries = _read(_own_settings)["hooks"]["PreToolUse"]
    assert sum(one == MINE for entry in entries for one in entry["hooks"]) == 1


def test_the_file_as_it_was_is_kept(_own_settings):
    _write(_own_settings, {"model": "opus"})

    h.install()

    kept = _own_settings.with_suffix(".json.before-sift")
    assert kept.is_file()
    assert json.loads(kept.read_text(encoding="utf-8")) == {"model": "opus"}


@pytest.mark.parametrize(
    ("written", "why"),
    [
        ("{ not json", "not JSON at all"),
        ('["a list"]', "JSON, but not an object"),
        ('{"hooks": "on"}', "hooks is not an object"),
        ('{"hooks": {"PreToolUse": "yes"}}', "the event is not a list"),
    ],
)
def test_a_shape_this_does_not_recognise_is_refused(_own_settings, written, why):
    """Refusing is the safety. This edits a file somebody else owns and may
    depend on; a merge that is not certain what it is merging into should not
    merge, and should say so rather than reshaping it."""
    _own_settings.write_text(written, encoding="utf-8")

    done, said = h.install()

    assert not done, why
    assert "sift:" in said
    assert _own_settings.read_text(encoding="utf-8") == written, "it wrote anyway"


def test_taking_it_out_leaves_everything_else(_own_settings):
    _write(
        _own_settings,
        {"model": "opus", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [THEIRS]}]}},
    )
    h.install()

    done, _ = h.uninstall()

    assert done
    after = _read(_own_settings)
    assert after["model"] == "opus"
    assert after["hooks"]["PreToolUse"][0]["hooks"] == [THEIRS]
    assert not h.installed()


def test_an_entry_that_was_only_ours_goes_with_it(_own_settings):
    """Leaving an empty matcher behind is leaving litter in somebody's file."""
    h.install()
    h.uninstall()

    assert _read(_own_settings)["hooks"]["PreToolUse"] == []


def test_taking_out_what_was_never_added_changes_nothing(_own_settings):
    _write(_own_settings, {"model": "opus"})

    done, said = h.uninstall()

    assert done
    assert "was not routed" in said


# -- how a person meets it --------------------------------------------------


def test_it_is_mentioned_once_and_then_never_again(capsys):
    cli.main(["run", "--", "echo", "one"])
    first = capsys.readouterr().err

    cli.main(["run", "--", "echo", "two"])
    second = capsys.readouterr().err

    assert "sift hook --install" in first
    assert "said once" in first
    assert "sift hook --install" not in second


def test_nothing_is_mentioned_once_it_is_on(capsys):
    h.install()

    cli.main(["run", "--", "echo", "one"])

    assert "sift hook --install" not in capsys.readouterr().err


def test_nothing_is_mentioned_to_somebody_who_switched_it_off(capsys, monkeypatch):
    monkeypatch.setenv("SIFT_HOOK", "0")

    cli.main(["run", "--", "echo", "one"])

    assert "sift hook --install" not in capsys.readouterr().err


def test_nobody_is_installed_over_without_being_asked(capsys, _own_settings):
    """No terminal and no `--yes` means nobody is there to answer, and this
    decides nothing on their behalf."""
    assert cli.main(["hook", "--install"]) == 1

    said = capsys.readouterr()
    assert "run twice" in said.out, "the offer is still shown"
    assert "--yes" in said.err
    assert not _own_settings.exists()


def test_yes_is_taken_as_the_answer(capsys, _own_settings):
    assert cli.main(["hook", "--install", "--yes"]) == 0

    assert h.installed()
    assert "routed here now" in capsys.readouterr().out
